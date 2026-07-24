"""IB Gateway connection layer (live account, READ-ONLY).

Design:
- GatewaySupervisor owns the lifecycle: connect → stream → on failure retry
  with exponential backoff (5s doubling to a 5-minute cap, never a tight loop).
- All raw ib_async objects are normalized to app.ibkr.types dataclasses and
  handed to a single listener (the live-state service).
- This build exposes no order-placement methods and refuses a configuration
  that is not marked read-only. The user must also enable IBKR's Read-Only API
  checkbox in Gateway; the client flag alone cannot prove that broker-side setting.
"""

import asyncio
import contextlib
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal

from ib_async import IB
from ib_async.contract import Contract
from ib_async.objects import AccountValue, Fill, PortfolioItem
from ib_async.order import Trade

from app.core.config import Settings
from app.core.logging import get_logger
from app.ibkr.types import (
    AccountSummaryData,
    CashBalanceData,
    ConnectionInfo,
    ExecutionData,
    GatewayState,
    InstrumentData,
    OrderData,
    PositionData,
    PriceQuality,
)
from app.services.account_binding import AccountBindingConfirmationRequiredError

log = get_logger(__name__)

BACKOFF_SCHEDULE_S = (5, 10, 20, 40, 80, 160, 300)

# IBKR account-value tags we map into AccountSummaryData
_SUMMARY_TAGS = {
    "NetLiquidation": "net_liquidation",
    "TotalCashValue": "total_cash",
    "GrossPositionValue": "gross_position_value",
    "BuyingPower": "buying_power",
    "AvailableFunds": "available_funds",
    "ExcessLiquidity": "excess_liquidity",
    "InitMarginReq": "init_margin",
    "MaintMarginReq": "maint_margin",
    "UnrealizedPnL": "unrealized_pnl",
    "RealizedPnL": "realized_pnl",
    "Leverage-S": "leverage",
}


class ReadOnlyViolation(RuntimeError):
    """Raised if anything attempts a non-readonly gateway connection."""


class MultipleGatewayAccountsError(RuntimeError):
    """The single-account appliance refuses an ambiguous linked-account session."""


def mask_account(account_id: str) -> str:
    if len(account_id) <= 4:
        return "***"
    return f"{account_id[0]}***{account_id[-3:]}"


class GatewayListener:
    """Interface the live-state service implements. All methods are async."""

    async def on_connection(self, info: ConnectionInfo) -> None: ...

    async def on_account_summary(self, data: AccountSummaryData) -> None: ...

    async def on_cash_balances(self, balances: list[CashBalanceData]) -> None: ...

    async def on_position(self, position: PositionData) -> None: ...

    async def on_execution(self, execution: ExecutionData) -> None: ...

    async def on_order(self, order: OrderData) -> None: ...


class GatewaySupervisor:
    def __init__(
        self,
        settings: Settings,
        listener: GatewayListener,
        ib_factory: Callable[[], IB] = IB,
        account_guard: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        if not settings.ibkr_readonly:
            raise ReadOnlyViolation(
                "This build only supports read-only gateway connections. "
                "IBKR_READONLY=false is refused by design — see SECURITY.md."
            )
        self._settings = settings
        self._listener = listener
        self._ib_factory = ib_factory
        self._account_guard = account_guard
        self._ib: IB | None = None
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()
        self._retry_now = asyncio.Event()
        self._flush_task: asyncio.Task | None = None
        self.info = ConnectionInfo(readonly=True)
        self._account_currency = settings.base_currency_fallback
        self._account_id = ""
        self._pending_account_id = ""
        self._binding_confirmation_id = ""
        self.binding_confirmation_required = False

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._run(), name="gateway-supervisor")

    async def stop(self) -> None:
        self._stopped.set()
        self._retry_now.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._disconnect()

    async def manual_reconnect(self) -> None:
        """User-triggered: skip the current backoff wait."""
        self.info.reconnect_attempts = 0
        self._retry_now.set()

    @property
    def account_id(self) -> str:
        """Raw account id for in-process binding checks; never return or log it."""
        return self._account_id

    @property
    def pending_account_id(self) -> str:
        """Raw pending id for local confirmation only; never return or log it."""
        return self._pending_account_id

    @property
    def binding_confirmation_id(self) -> str:
        """Opaque browser confirmation id; it contains no account identifier."""
        return self._binding_confirmation_id

    def pending_account_for_confirmation(self, confirmation_id: str) -> str:
        """Resolve only the exact account candidate represented in the browser."""
        if (
            not self.binding_confirmation_required
            or not confirmation_id
            or not self._binding_confirmation_id
            or not secrets.compare_digest(confirmation_id, self._binding_confirmation_id)
        ):
            return ""
        return self._pending_account_id

    def complete_binding_confirmation(self, confirmation_id: str, account_id: str) -> None:
        """Clear a confirmation only if it still refers to the captured account."""
        if (
            self.pending_account_for_confirmation(confirmation_id) == account_id
            and self._pending_account_id == account_id
        ):
            self._clear_pending_binding_confirmation()

    async def fetch_daily_bars(self, conid: int, duration: str = "6 M") -> list[dict]:
        """Read-only historical daily bars for one instrument. Returns a plain
        list of {date, open, high, low, close, volume} dicts (empty if the
        gateway is down or the contract can't be resolved). Historical data is
        a read request — consistent with the read-only guarantee."""
        ib = self._ib
        if ib is None or not ib.isConnected():
            return []
        try:
            contracts = await ib.qualifyContractsAsync(Contract(conId=conid))
            if not contracts:
                return []
            bars = await ib.reqHistoricalDataAsync(
                contracts[0],
                endDateTime="",
                durationStr=duration,
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
        except Exception as exc:  # pacing violation, no permission, etc.
            log.warning("historical_bars_failed", conid=conid, error=str(exc))
            return []
        out: list[dict] = []
        for b in bars or []:
            d = b.date
            out.append(
                {
                    "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                    "open": float(b.open),
                    "high": float(b.high),
                    "low": float(b.low),
                    "close": float(b.close),
                    "volume": float(b.volume) if b.volume is not None else None,
                }
            )
        return out

    async def _run(self) -> None:
        attempt = 0
        while not self._stopped.is_set():
            try:
                await self._set_state(GatewayState.CONNECTING)
                await self._connect()
                attempt = 0
                await self._stream_until_disconnect()
            except ConnectionRefusedError:
                await self._set_state(
                    GatewayState.GATEWAY_DOWN, error="IB Gateway is not reachable (TCP refused)"
                )
            except TimeoutError:
                await self._set_state(
                    GatewayState.AUTH_REQUIRED,
                    error="Gateway reachable but API handshake timed out — is the session logged in?",
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — supervisor must survive anything
                await self._set_state(
                    GatewayState.DISCONNECTED, error=f"{type(exc).__name__}: {exc}"
                )
            finally:
                await self._disconnect()

            if self._stopped.is_set():
                break
            delay = BACKOFF_SCHEDULE_S[min(attempt, len(BACKOFF_SCHEDULE_S) - 1)]
            attempt += 1
            self.info.reconnect_attempts = attempt
            self.info.next_retry_in_s = delay
            log.info("gateway_retry_scheduled", delay_s=delay, attempt=attempt)
            self._retry_now.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._retry_now.wait(), timeout=delay)

    async def _connect(self) -> None:
        s = self._settings
        self._ib = self._ib_factory()
        # This keeps ib_async startup in read-only mode. Order safety ultimately
        # relies on the absence of order APIs here plus Gateway's Read-Only checkbox.
        await self._ib.connectAsync(
            host=s.ibkr_gateway_host,
            port=s.ibkr_gateway_port,
            clientId=s.ibkr_client_id,
            readonly=True,
            timeout=15,
        )
        accounts = self._ib.managedAccounts()
        if len(accounts) != 1:
            self._clear_pending_binding_confirmation()
            self.info.account_id_masked = None
            raise MultipleGatewayAccountsError(
                "Exactly one IBKR account must be available; use a username scoped to one account"
            )
        account = accounts[0]
        if self._account_guard is not None:
            try:
                await self._account_guard(account)
            except AccountBindingConfirmationRequiredError:
                if self._pending_account_id != account:
                    self._binding_confirmation_id = ""
                self._pending_account_id = account
                # Legacy non-empty databases need to show the candidate account
                # for explicit confirmation. No data is ingested in this state.
                self.info.account_id_masked = mask_account(account)
                self.binding_confirmation_required = True
                if not self._binding_confirmation_id:
                    self._binding_confirmation_id = secrets.token_urlsafe(24)
                raise
            except Exception:
                self._clear_pending_binding_confirmation()
                # Never label already-stored data with a rejected account.
                self.info.account_id_masked = (
                    mask_account(self._account_id) if self._account_id else None
                )
                raise
        self._clear_pending_binding_confirmation()
        self._account_id = account
        self.info.account_id_masked = mask_account(account)
        self.info.connected_since = datetime.now(UTC)
        self.info.next_retry_in_s = None
        self._wire_events(self._ib)
        with contextlib.suppress(Exception):
            self._ib.reqPnL(account)
        await self._set_state(GatewayState.CONNECTED)
        log.info("gateway_connected", account=self.info.account_id_masked, readonly=True)
        await self._push_initial_state()

    async def _stream_until_disconnect(self) -> None:
        assert self._ib is not None
        disconnected = asyncio.Event()
        self._ib.disconnectedEvent += lambda: disconnected.set()
        await disconnected.wait()
        if not self._stopped.is_set():
            await self._set_state(GatewayState.DISCONNECTED, error="Gateway connection lost")

    async def _disconnect(self) -> None:
        if self._ib is not None:
            with contextlib.suppress(Exception):
                self._ib.disconnect()
            self._ib = None

    def _clear_pending_binding_confirmation(self) -> None:
        self._pending_account_id = ""
        self._binding_confirmation_id = ""
        self.binding_confirmation_required = False

    # -- event wiring and normalization -------------------------------------

    def _wire_events(self, ib: IB) -> None:
        ib.accountValueEvent += self._on_account_value
        ib.updatePortfolioEvent += self._on_portfolio_item
        ib.execDetailsEvent += self._on_exec_details
        ib.orderStatusEvent += self._on_order_status
        ib.pnlEvent += self._on_pnl
        ib.errorEvent += self._on_error

    async def _push_initial_state(self) -> None:
        """After (re)connect, push the full current state once."""
        assert self._ib is not None
        for item in self._ib.portfolio():
            self._on_portfolio_item(item)
        await self._emit_account_summary()
        await self._emit_cash_balances()
        for trade in self._ib.openTrades():
            self._on_order_status(trade)
        for fill in self._ib.fills():
            self._on_exec_details(None, fill)
        # Session buffer (fills()) is short; ask the gateway for every execution
        # it still holds (typically recent days). Full history still needs Flex.
        await self._request_executions()

    async def _request_executions(self) -> None:
        assert self._ib is not None
        try:
            from ib_async import ExecutionFilter

            fills = await self._ib.reqExecutionsAsync(ExecutionFilter(acctCode=self._account_id))
        except Exception as exc:  # noqa: BLE001 — never fail connect because of blotter pull
            log.warning("gateway_executions_failed", error=str(exc))
            return
        for fill in fills or []:
            self._on_exec_details(None, fill)
        log.info("gateway_executions_loaded", count=len(fills or []))

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract=None) -> None:
        # 2104/2106/2158 are "connection OK" notices; 10167/10197 delayed-data notices
        if errorCode in (2104, 2106, 2107, 2158):
            return
        if errorCode in (10167, 10197, 354):
            self.info.market_data_type = "delayed"
            log.info("market_data_delayed", code=errorCode)
            return
        log.warning("gateway_error", code=errorCode, message=errorString, req_id=reqId)
        self.info.last_error = f"[{errorCode}] {errorString}"

    def _on_account_value(self, av: AccountValue) -> None:
        if self._account_id and av.account != self._account_id:
            return
        if av.tag == "NetLiquidation" and av.currency and av.currency != "BASE":
            self._account_currency = av.currency
        self._schedule_flush()

    def _on_pnl(self, pnl) -> None:
        if self._account_id and getattr(pnl, "account", "") != self._account_id:
            return
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        """Account values arrive in bursts; coalesce into one summary emit."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_soon())

    async def _flush_soon(self) -> None:
        await asyncio.sleep(0.5)
        await self._emit_account_summary()
        await self._emit_cash_balances()

    async def _emit_account_summary(self) -> None:
        if self._ib is None:
            return
        values: dict[str, Decimal] = {}
        for av in self._ib.accountValues():
            if self._account_id and av.account != self._account_id:
                continue
            if av.tag in _SUMMARY_TAGS and av.currency in ("", self._account_currency, "BASE"):
                with contextlib.suppress(ArithmeticError, ValueError):
                    values[_SUMMARY_TAGS[av.tag]] = Decimal(av.value)
        daily_pnl = None
        pnl_list = [
            pnl
            for pnl in self._ib.pnl()
            if not self._account_id or getattr(pnl, "account", "") == self._account_id
        ]
        if pnl_list and pnl_list[0].dailyPnL == pnl_list[0].dailyPnL:  # not NaN
            daily_pnl = Decimal(str(pnl_list[0].dailyPnL))
        data = AccountSummaryData(
            ts=datetime.now(UTC),
            base_currency=self._account_currency,
            daily_pnl=daily_pnl,
            **values,
        )
        self.info.last_update = data.ts
        await self._listener.on_account_summary(data)

    async def _emit_cash_balances(self) -> None:
        if self._ib is None:
            return
        by_ccy: dict[str, dict[str, Decimal]] = {}
        for av in self._ib.accountValues():
            if self._account_id and av.account != self._account_id:
                continue
            if av.tag in ("CashBalance", "SettledCash", "NetLiquidationByCurrency", "ExchangeRate"):
                if not av.currency or av.currency == "BASE":
                    continue
                with contextlib.suppress(ArithmeticError, ValueError):
                    by_ccy.setdefault(av.currency, {})[av.tag] = Decimal(av.value)
        ts = datetime.now(UTC)
        balances = [
            CashBalanceData(
                ts=ts,
                currency=ccy,
                cash_balance=vals.get("CashBalance", Decimal(0)),
                settled_cash=vals.get("SettledCash"),
                nlv_in_ccy=vals.get("NetLiquidationByCurrency"),
                fx_rate_to_base=vals.get("ExchangeRate"),
            )
            for ccy, vals in sorted(by_ccy.items())
        ]
        if balances:
            await self._listener.on_cash_balances(balances)

    def _on_portfolio_item(self, item: PortfolioItem) -> None:
        if self._account_id and item.account != self._account_id:
            return
        c = item.contract
        pos = PositionData(
            ts=datetime.now(UTC),
            instrument=_instrument(c),
            quantity=Decimal(str(item.position)),
            avg_cost=Decimal(str(item.averageCost))
            if item.averageCost == item.averageCost
            else None,
            market_price=Decimal(str(item.marketPrice))
            if item.marketPrice == item.marketPrice
            else None,
            market_value=Decimal(str(item.marketValue))
            if item.marketValue == item.marketValue
            else None,
            unrealized_pnl=(
                Decimal(str(item.unrealizedPNL))
                if item.unrealizedPNL == item.unrealizedPNL
                else None
            ),
            price_quality=(
                PriceQuality.DELAYED
                if self.info.market_data_type == "delayed"
                else PriceQuality.UNKNOWN
            ),
        )
        self.info.last_update = pos.ts
        asyncio.ensure_future(self._listener.on_position(pos))

    def _on_exec_details(self, _trade, fill: Fill) -> None:
        ex = fill.execution
        if self._account_id and ex.acctNumber != self._account_id:
            return
        commission = None
        commission_ccy = None
        realized = None
        if (
            fill.commissionReport
            and fill.commissionReport.commission == fill.commissionReport.commission
        ):
            commission = Decimal(str(fill.commissionReport.commission))
            commission_ccy = fill.commissionReport.currency or None
            if fill.commissionReport.realizedPNL == fill.commissionReport.realizedPNL:
                realized = Decimal(str(fill.commissionReport.realizedPNL))
        data = ExecutionData(
            exec_id=ex.execId,
            instrument=_instrument(fill.contract),
            side="BUY" if ex.side.upper().startswith("B") else "SELL",
            quantity=Decimal(str(ex.shares)),
            price=Decimal(str(ex.price)),
            trade_time=ex.time if ex.time.tzinfo else ex.time.replace(tzinfo=UTC),
            order_id=str(ex.orderId) if ex.orderId else None,
            perm_id=str(ex.permId) if ex.permId else None,
            exchange=ex.exchange or None,
            commission=commission,
            commission_currency=commission_ccy,
            realized_pnl_ib=realized,
        )
        asyncio.ensure_future(self._listener.on_execution(data))

    def _on_order_status(self, trade: Trade) -> None:
        o, st = trade.order, trade.orderStatus
        if self._account_id and o.account != self._account_id:
            return
        data = OrderData(
            perm_id=str(o.permId or o.orderId),
            status=st.status,
            instrument=_instrument(trade.contract) if trade.contract else None,
            side=o.action or None,
            order_type=o.orderType or None,
            limit_price=Decimal(str(o.lmtPrice)) if o.lmtPrice and o.lmtPrice < 1e300 else None,
            aux_price=Decimal(str(o.auxPrice)) if o.auxPrice and o.auxPrice < 1e300 else None,
            tif=o.tif or None,
            quantity=Decimal(str(o.totalQuantity)) if o.totalQuantity else None,
            filled=Decimal(str(st.filled)) if st.filled == st.filled else None,
            remaining=Decimal(str(st.remaining)) if st.remaining == st.remaining else None,
        )
        asyncio.ensure_future(self._listener.on_order(data))

    async def _set_state(self, state: GatewayState, error: str | None = None) -> None:
        self.info.state = state
        if error:
            self.info.last_error = error
            log.warning("gateway_state", state=state.value, error=error)
        else:
            log.info("gateway_state", state=state.value)
        await self._listener.on_connection(self.info)


def _instrument(c: Contract) -> InstrumentData:
    return InstrumentData(
        conid=c.conId,
        symbol=c.symbol or c.localSymbol or str(c.conId),
        sec_type=c.secType or "STK",
        currency=c.currency or "USD",
        name=getattr(c, "description", None) or None,
        exchange=c.primaryExchange or c.exchange or None,
    )
