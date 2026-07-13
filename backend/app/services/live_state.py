"""Live account state: in-memory truth for the UI + persistence to Postgres.

Implements GatewayListener. On every normalized event it:
1. updates the in-memory state (what the REST API serves),
2. publishes a small delta to the WebSocket hub,
3. persists what must survive restarts (instruments, executions, orders
   immediately; account snapshots on a fixed cadence).

On disconnect nothing is reset — the last data stays, marked stale via the
connection info the UI polls/receives.
"""

import asyncio
import contextlib
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import (
    AccountSnapshot,
    CashBalance,
    Execution,
    Instrument,
    Order,
    Position,
)
from app.ibkr.gateway import GatewayListener
from app.ibkr.types import (
    AccountSummaryData,
    CashBalanceData,
    ConnectionInfo,
    ExecutionData,
    GatewayState,
    InstrumentData,
    OrderData,
    PositionData,
)
from app.ws.hub import WsHub

log = get_logger(__name__)


class LiveStateService(GatewayListener):
    def __init__(self, hub: WsHub, snapshot_interval_min: int = 15) -> None:
        self._hub = hub
        self._snapshot_interval_min = snapshot_interval_min
        self._snapshot_task: asyncio.Task | None = None

        self.connection = ConnectionInfo()
        self.account: AccountSummaryData | None = None
        self.balances: list[CashBalanceData] = []
        self.positions: dict[int, PositionData] = {}
        self.orders: dict[str, OrderData] = {}

    # -- GatewayListener ----------------------------------------------------

    async def on_connection(self, info: ConnectionInfo) -> None:
        self.connection = info
        await self._hub.publish("connection", _connection_payload(info))
        if info.state == GatewayState.CONNECTED and self._snapshot_task is None:
            self._snapshot_task = asyncio.create_task(self._snapshot_loop())

    async def on_account_summary(self, data: AccountSummaryData) -> None:
        self.account = data
        await self._hub.publish("account_summary", _clean(asdict(data)))

    async def on_cash_balances(self, balances: list[CashBalanceData]) -> None:
        self.balances = balances
        await self._hub.publish("cash_balances", {"balances": [_clean(asdict(b)) for b in balances]})

    async def on_position(self, position: PositionData) -> None:
        self.positions[position.instrument.conid] = position
        await self._hub.publish(
            f"position:{position.instrument.conid}", _clean(asdict(position))
        )
        await self._persist_position(position)

    async def on_execution(self, execution: ExecutionData) -> None:
        await self._hub.publish("execution", _clean(asdict(execution)))
        await self._persist_execution(execution)

    async def on_order(self, order: OrderData) -> None:
        self.orders[order.perm_id] = order
        await self._hub.publish(f"order:{order.perm_id}", _clean(asdict(order)))
        await self._persist_order(order)

    # -- persistence ---------------------------------------------------------

    async def _upsert_instrument(self, session, inst: InstrumentData) -> None:
        stmt = pg_insert(Instrument).values(
            conid=inst.conid,
            symbol=inst.symbol,
            name=inst.name,
            sec_type=inst.sec_type,
            currency=inst.currency,
            exchange=inst.exchange,
            updated_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Instrument.conid],
            set_={"symbol": stmt.excluded.symbol, "updated_at": stmt.excluded.updated_at},
        )
        await session.execute(stmt)

    async def _persist_position(self, p: PositionData) -> None:
        try:
            async with db_session() as session:
                await self._upsert_instrument(session, p.instrument)
                stmt = pg_insert(Position).values(
                    conid=p.instrument.conid,
                    quantity=p.quantity,
                    avg_cost=p.avg_cost,
                    market_price=p.market_price,
                    market_value=p.market_value,
                    unrealized_pnl=p.unrealized_pnl,
                    daily_pnl=p.daily_pnl,
                    currency=p.instrument.currency,
                    price_quality=p.price_quality.value,
                    is_open=p.quantity != 0,
                    updated_at=p.ts,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Position.conid],
                    set_={
                        c: getattr(stmt.excluded, c)
                        for c in (
                            "quantity", "avg_cost", "market_price", "market_value",
                            "unrealized_pnl", "daily_pnl", "price_quality", "is_open",
                            "updated_at",
                        )
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("persist_position_failed", conid=p.instrument.conid)

    async def _persist_execution(self, e: ExecutionData) -> None:
        try:
            async with db_session() as session:
                await self._upsert_instrument(session, e.instrument)
                stmt = pg_insert(Execution).values(
                    exec_id=e.exec_id,
                    order_id=e.order_id,
                    perm_id=e.perm_id,
                    conid=e.instrument.conid,
                    side=e.side,
                    quantity=e.quantity,
                    price=e.price,
                    trade_time=e.trade_time,
                    exchange=e.exchange,
                    commission=e.commission,
                    commission_currency=e.commission_currency,
                    realized_pnl_ib=e.realized_pnl_ib,
                    currency=e.instrument.currency,
                    source="gateway",
                    updated_at=datetime.now(UTC),
                )
                # Flex data is richer; never let a live event overwrite flex rows.
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Execution.exec_id],
                    set_={
                        "commission": stmt.excluded.commission,
                        "realized_pnl_ib": stmt.excluded.realized_pnl_ib,
                        "updated_at": stmt.excluded.updated_at,
                    },
                    where=(Execution.source == "gateway"),
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("persist_execution_failed", exec_id=e.exec_id)

    async def _persist_order(self, o: OrderData) -> None:
        try:
            async with db_session() as session:
                if o.instrument:
                    await self._upsert_instrument(session, o.instrument)
                stmt = pg_insert(Order).values(
                    perm_id=o.perm_id,
                    conid=o.instrument.conid if o.instrument else None,
                    status=o.status,
                    side=o.side,
                    order_type=o.order_type,
                    limit_price=o.limit_price,
                    aux_price=o.aux_price,
                    tif=o.tif,
                    quantity=o.quantity,
                    filled=o.filled,
                    remaining=o.remaining,
                    source="gateway",
                    updated_at=datetime.now(UTC),
                )
                update_cols = ("status", "filled", "remaining", "updated_at")
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Order.perm_id],
                    set_={c: getattr(stmt.excluded, c) for c in update_cols},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("persist_order_failed", perm_id=o.perm_id)

    async def _snapshot_loop(self) -> None:
        if self._snapshot_interval_min <= 0:
            return
        while True:
            await asyncio.sleep(self._snapshot_interval_min * 60)
            with contextlib.suppress(Exception):
                await self.persist_snapshot()

    async def persist_snapshot(self) -> None:
        """Save the current account summary + cash balances as history."""
        if self.account is None:
            return
        a = self.account
        async with db_session() as session:
            session.add(
                AccountSnapshot(
                    ts=a.ts,
                    net_liquidation=a.net_liquidation or 0,
                    total_cash=a.total_cash,
                    gross_position_value=a.gross_position_value,
                    buying_power=a.buying_power,
                    available_funds=a.available_funds,
                    excess_liquidity=a.excess_liquidity,
                    init_margin=a.init_margin,
                    maint_margin=a.maint_margin,
                    unrealized_pnl=a.unrealized_pnl,
                    realized_pnl=a.realized_pnl,
                    leverage=a.leverage,
                    base_currency=a.base_currency,
                    data_quality="realtime"
                    if self.connection.state == GatewayState.CONNECTED
                    else "stale",
                )
            )
            for b in self.balances:
                session.add(
                    CashBalance(
                        ts=b.ts,
                        currency=b.currency,
                        cash_balance=b.cash_balance,
                        settled_cash=b.settled_cash,
                        nlv_in_ccy=b.nlv_in_ccy,
                        fx_rate_to_base=b.fx_rate_to_base,
                    )
                )
            await session.commit()
        log.info("snapshot_persisted", nlv=str(a.net_liquidation))


def _clean(d: dict) -> dict:
    """dataclass asdict → JSON-friendly (Decimal/datetime/enum via str)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _clean(v)
        elif hasattr(v, "value") and not isinstance(v, int | float | str):
            out[k] = v.value
        else:
            out[k] = str(v) if v is not None and not isinstance(v, int | float | str | bool) else v
    return out


def _connection_payload(info: ConnectionInfo) -> dict:
    return {
        "state": info.state.value,
        "readonly": info.readonly,
        "account": info.account_id_masked,
        "connected_since": info.connected_since.isoformat() if info.connected_since else None,
        "last_update": info.last_update.isoformat() if info.last_update else None,
        "last_error": info.last_error,
        "reconnect_attempts": info.reconnect_attempts,
        "next_retry_in_s": info.next_retry_in_s,
        "market_data_type": info.market_data_type,
    }
