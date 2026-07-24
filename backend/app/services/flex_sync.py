"""Historical sync: Flex report → idempotent upserts into Postgres.

Every record carries IBKR's natural id, so re-running a sync can never
duplicate data. Retroactive corrections from IBKR (e.g. adjusted commission)
overwrite the stored row and are counted, never silently ignored — the sync
run records how many rows were inserted vs updated vs unchanged.
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import (
    CashTransaction,
    CorporateAction,
    DailyEquity,
    Execution,
    FxRate,
    Instrument,
    SyncRun,
)
from app.ibkr.flex import FlexClient
from app.ibkr.flex_parser import FlexInstrument, FlexReport, parse_flex_report
from app.services.account_binding import (
    account_binding_exists,
    assert_account_matches_binding,
)
from app.services.flex_cooldown import (
    FlexAttemptBlocked,
    FlexCooldownActive,
    get_active_flex_cooldown,
    get_flex_attempt_block,
    lockout_error_details,
)

log = get_logger(__name__)

_DEPOSIT_TYPES = {"DEPOSIT", "WITHDRAWAL"}
_FLEX_ADVISORY_LOCK_KEY = 0x49424B52464C4558  # "IBKRFLEX", within signed bigint


class SyncAlreadyRunning(RuntimeError):
    pass


class FlexAccountMismatchError(ValueError):
    """The Flex report belongs to a different account than the live Gateway."""


def validate_flex_account(report_account_id: str | None, gateway_account_id: str) -> None:
    if not report_account_id:
        raise FlexAccountMismatchError("Flex report does not identify exactly one account")
    if gateway_account_id and report_account_id != gateway_account_id:
        raise FlexAccountMismatchError(
            "Flex report account does not match the connected IB Gateway account"
        )


class FlexSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token = (settings.ibkr_flex_token or "").strip()
        self._query_id = (settings.ibkr_flex_query_id or "").strip()
        self._running = False

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._query_id)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def autosync_enabled(self) -> bool:
        return self._settings.ibkr_flex_autosync

    @property
    def token(self) -> str:
        return self._token

    @property
    def query_id(self) -> str:
        return self._query_id

    def set_credentials(self, token: str, query_id: str) -> None:
        """Hot-reload credentials (from UI/DB) without restarting the process."""
        self._token = (token or "").strip()
        self._query_id = (query_id or "").strip()

    async def run(self, trigger: str = "manual") -> int:
        """Full sync flow with durable cooldown and cross-process serialization."""
        # Snapshot credentials before the first await. A UI save during this run
        # affects only the next run, never half of the current request.
        token = self._token
        query_id = self._query_id
        if not token or not query_id:
            raise ValueError("Flex token and query id are required")
        if not await account_binding_exists():
            from app.services.account_binding import AccountBindingRequiredError

            raise AccountBindingRequiredError(
                "Connect one IB Gateway account before importing Flex history"
            )
        if self._running:
            raise SyncAlreadyRunning("a sync is already in progress")
        # Set this before the first await so concurrent tasks in this process
        # cannot both pass the check above.
        self._running = True
        try:
            async with db_session() as guard_session:
                lock_acquired = await _try_acquire_flex_lock(guard_session)
                if not lock_acquired:
                    raise SyncAlreadyRunning("a sync is already running in another process")
                try:
                    cooldown = await get_active_flex_cooldown(guard_session)
                    if cooldown:
                        raise FlexCooldownActive(cooldown)
                    attempt_block = await get_flex_attempt_block(guard_session)
                    if attempt_block:
                        raise FlexAttemptBlocked(attempt_block)
                    return await self._run_inner(trigger, token=token, query_id=query_id)
                finally:
                    await _release_flex_lock(guard_session, lock_acquired)
        finally:
            self._running = False

    async def _run_inner(self, trigger: str, *, token: str, query_id: str) -> int:
        async with db_session() as session:
            run = SyncRun(kind="flex_full", started_at=datetime.now(UTC), status="running")
            session.add(run)
            await session.commit()
            run_id = run.id

        try:
            client = FlexClient(
                token=token,
                query_id=query_id,
            )
            statement = await client.fetch_statement()
            report = parse_flex_report(statement.xml)
            await assert_account_matches_binding(report.account_id)
            from app.services import registry

            gateway_account_id = (
                registry.supervisor.account_id if registry.supervisor is not None else ""
            )
            validate_flex_account(report.account_id, gateway_account_id)
            counts = await self.ingest(report)
            async with db_session() as session:
                run = await session.get(SyncRun, run_id)
                assert run is not None
                run.finished_at = datetime.now(UTC)
                run.status = "ok"
                run.date_range_from = report.from_date.isoformat() if report.from_date else None
                run.date_range_to = report.to_date.isoformat() if report.to_date else None
                run.records_upserted = counts["upserted"]
                run.records_skipped = counts["unchanged"]
                run.errors = (
                    {"parse_skipped": report.skipped, "trigger": trigger}
                    if report.skipped
                    else {"trigger": trigger}
                )
                await session.commit()
            log.info("flex_sync_ok", run_id=run_id, **counts)
            # Journal / performance views need FIFO cycles — rebuild after history lands.
            try:
                from app.services.trade_cycles import rebuild_cycles

                cycle_counts = await rebuild_cycles()
                log.info("cycles_rebuilt_after_flex", run_id=run_id, **cycle_counts)
            except Exception:  # noqa: BLE001 — sync itself succeeded; cycles can be rebuilt manually
                log.exception("cycles_rebuild_after_flex_failed", run_id=run_id)
            return run_id
        except asyncio.CancelledError:
            failed_at = datetime.now(UTC)
            async with db_session() as session:
                run = await session.get(SyncRun, run_id)
                if run is not None:
                    run.finished_at = failed_at
                    run.status = "failed"
                    run.errors = {
                        "error": "Flex sync interrupted during shutdown",
                        "error_code": "interrupted",
                        "error_type": "CancelledError",
                        "trigger": trigger,
                    }
                    await session.commit()
            log.warning("flex_sync_interrupted", run_id=run_id)
            raise
        except Exception as exc:
            from app.ibkr.flex_help import explain_flex_error

            failed_at = datetime.now(UTC)
            explained = explain_flex_error(exc)
            async with db_session() as session:
                run = await session.get(SyncRun, run_id)
                if run is not None:
                    run.finished_at = failed_at
                    run.status = "failed"
                    error_details = lockout_error_details(
                        exc,
                        trigger=trigger,
                        failed_at=failed_at,
                    )
                    error_details["help_he"] = explained["help_he"]
                    if explained["code"] != "?":
                        # Keep the upstream key for older UI clients while the
                        # hardened API treats error_code as canonical.
                        error_details["code"] = explained["code"]
                    run.errors = error_details
                    await session.commit()
            log.exception(
                "flex_sync_failed",
                run_id=run_id,
                flex_code=None if explained["code"] == "?" else explained["code"],
            )
            raise

    # ── ingestion (idempotent) ───────────────────────────

    async def ingest(self, report: FlexReport) -> dict[str, int]:
        """Upsert a parsed report. Public so tests can feed fixture XML."""
        upserted = 0
        unchanged = 0
        async with db_session() as session:
            instruments: dict[int, FlexInstrument] = {}
            for t in report.trades:
                instruments[t.instrument.conid] = t.instrument
            for p in report.open_positions:
                instruments[p.instrument.conid] = p.instrument
            for c in report.cash_transactions:
                if c.instrument:
                    instruments[c.instrument.conid] = c.instrument
            for inst in instruments.values():
                await _upsert_instrument(session, inst)

            for t in report.trades:
                changed = await _upsert_execution(session, t)
                upserted += changed
                unchanged += 1 - changed

            for c in report.cash_transactions:
                changed = await _upsert_cash(session, c)
                upserted += changed
                unchanged += 1 - changed

            deposits_by_date = await _aggregate_flows(session)

            for e in report.equity_summaries:
                changed = await _upsert_daily_equity(session, e, deposits_by_date)
                upserted += changed
                unchanged += 1 - changed

            for ca in report.corporate_actions:
                await _upsert_corporate_action(session, ca)
                upserted += 1

            for fx in report.fx_rates:
                await _upsert_fx_rate(session, fx)
                upserted += 1

            await session.commit()

        return {"upserted": upserted, "unchanged": unchanged}


async def _try_acquire_flex_lock(session: AsyncSession) -> bool:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return True
    acquired = (
        await session.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": _FLEX_ADVISORY_LOCK_KEY},
        )
    ).scalar_one()
    return bool(acquired)


async def _release_flex_lock(session: AsyncSession, acquired: bool) -> None:
    if not acquired or session.get_bind().dialect.name != "postgresql":
        return
    try:
        await session.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": _FLEX_ADVISORY_LOCK_KEY},
        )
    except Exception:  # noqa: BLE001 — connection close also releases session locks
        log.warning("flex_advisory_unlock_failed")


# ── row-level upserts ─────────────────────────────────────


async def _upsert_instrument(session: AsyncSession, inst: FlexInstrument) -> None:
    stmt = pg_insert(Instrument).values(
        conid=inst.conid,
        symbol=inst.symbol,
        name=inst.name,
        sec_type=inst.sec_type,
        currency=inst.currency,
        exchange=inst.exchange,
        classification_source="flex",
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Instrument.conid],
        set_={
            "symbol": stmt.excluded.symbol,
            "name": func.coalesce(stmt.excluded.name, Instrument.name),
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.execute(stmt)


async def _upsert_execution(session: AsyncSession, t) -> int:
    """Returns 1 if the row was inserted or materially changed, else 0."""
    existing = await session.get(Execution, t.exec_id)
    if existing is not None and existing.source == "flex" and existing.commission == t.commission:
        return 0
    stmt = pg_insert(Execution).values(
        exec_id=t.exec_id,
        order_id=t.order_id,
        conid=t.instrument.conid,
        side=t.side,
        quantity=t.quantity,
        price=t.price,
        trade_time=t.trade_time,
        exchange=t.exchange,
        order_type=t.order_type,
        commission=t.commission,
        commission_currency=t.commission_currency,
        realized_pnl_ib=t.realized_pnl,
        currency=t.instrument.currency,
        fx_rate_to_base=t.fx_rate_to_base,
        net_amount=t.net_amount,
        source="flex",
        updated_at=datetime.now(UTC),
    )
    # Flex is the richer/authoritative source → it may overwrite gateway rows.
    stmt = stmt.on_conflict_do_update(
        index_elements=[Execution.exec_id],
        set_={
            c: getattr(stmt.excluded, c)
            for c in (
                "order_id",
                "commission",
                "commission_currency",
                "realized_pnl_ib",
                "fx_rate_to_base",
                "net_amount",
                "order_type",
                "source",
                "updated_at",
            )
        },
    )
    await session.execute(stmt)
    return 1


async def _upsert_cash(session: AsyncSession, c) -> int:
    existing = await session.get(CashTransaction, c.transaction_id)
    if existing is not None and existing.amount == c.amount:
        return 0
    stmt = pg_insert(CashTransaction).values(
        transaction_id=c.transaction_id,
        type=c.type,
        amount=c.amount,
        currency=c.currency,
        fx_rate_to_base=c.fx_rate_to_base,
        tx_datetime=c.tx_datetime,
        settle_date=c.settle_date,
        conid=c.conid if c.instrument else None,
        description=c.description,
        source="flex",
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[CashTransaction.transaction_id],
        set_={"amount": stmt.excluded.amount, "updated_at": stmt.excluded.updated_at},
    )
    await session.execute(stmt)
    return 1


async def _aggregate_flows(session: AsyncSession) -> dict:
    """date → (deposits, withdrawals) in base currency, from cash transactions."""
    rows = (
        await session.execute(
            select(
                func.date(CashTransaction.tx_datetime),
                CashTransaction.type,
                func.sum(
                    CashTransaction.amount * func.coalesce(CashTransaction.fx_rate_to_base, 1)
                ),
            )
            .where(CashTransaction.type.in_(_DEPOSIT_TYPES))
            .group_by(func.date(CashTransaction.tx_datetime), CashTransaction.type)
        )
    ).all()
    result: dict = {}
    for d, tx_type, total in rows:
        entry = result.setdefault(d, {"deposits": Decimal(0), "withdrawals": Decimal(0)})
        if tx_type == "DEPOSIT":
            entry["deposits"] += total
        else:
            entry["withdrawals"] += abs(total)
    return result


async def _upsert_daily_equity(session: AsyncSession, e, flows: dict) -> int:
    line = f"{e.report_date}|{e.total}|{e.cash}|{e.stock}"
    line_hash = hashlib.sha256(line.encode()).hexdigest()[:16]
    existing = await session.get(DailyEquity, e.report_date)
    if existing is not None and existing.source_line_hash == line_hash:
        return 0
    day_flows = flows.get(e.report_date, {})
    stmt = pg_insert(DailyEquity).values(
        equity_date=e.report_date,
        nav=e.total,
        cash=e.cash,
        stock_value=e.stock,
        dividend_accruals=e.dividend_accruals,
        interest_accruals=e.interest_accruals,
        deposits=day_flows.get("deposits", 0),
        withdrawals=day_flows.get("withdrawals", 0),
        source="flex",
        source_line_hash=line_hash,
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyEquity.equity_date],
        set_={
            c: getattr(stmt.excluded, c)
            for c in (
                "nav",
                "cash",
                "stock_value",
                "dividend_accruals",
                "interest_accruals",
                "deposits",
                "withdrawals",
                "source_line_hash",
                "updated_at",
            )
        },
    )
    await session.execute(stmt)
    return 1


async def _upsert_corporate_action(session: AsyncSession, ca) -> None:
    if ca.instrument:
        await _upsert_instrument(session, ca.instrument)
    stmt = pg_insert(CorporateAction).values(
        action_id=ca.action_id,
        type=ca.type or "UNKNOWN",
        conid=ca.conid if ca.instrument else None,
        ex_date=ca.ex_date,
        pay_date=ca.pay_date,
        description=ca.description,
        source="flex",
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[CorporateAction.action_id],
        set_={"description": stmt.excluded.description, "updated_at": stmt.excluded.updated_at},
    )
    await session.execute(stmt)


async def _upsert_fx_rate(session: AsyncSession, fx) -> None:
    stmt = pg_insert(FxRate).values(
        rate_date=fx.report_date,
        currency=fx.currency,
        rate_to_base=fx.rate_to_base,
        source="flex",
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fx_date_ccy",
        set_={"rate_to_base": stmt.excluded.rate_to_base},
    )
    await session.execute(stmt)
