"""Historical sync: Flex report → idempotent upserts into Postgres.

Every record carries IBKR's natural id, so re-running a sync can never
duplicate data. Retroactive corrections from IBKR (e.g. adjusted commission)
overwrite the stored row and are counted, never silently ignored — the sync
run records how many rows were inserted vs updated vs unchanged.
"""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
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

log = get_logger(__name__)

_DEPOSIT_TYPES = {"DEPOSIT", "WITHDRAWAL"}


class SyncAlreadyRunning(RuntimeError):
    pass


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
        """Full sync flow. Returns the sync_run id."""
        if self._running:
            raise SyncAlreadyRunning("a sync is already in progress")
        self._running = True
        try:
            return await self._run_inner(trigger)
        finally:
            self._running = False

    async def _run_inner(self, trigger: str) -> int:
        async with db_session() as session:
            run = SyncRun(kind="flex_full", started_at=datetime.now(UTC), status="running")
            session.add(run)
            await session.commit()
            run_id = run.id

        try:
            client = FlexClient(
                token=self._token,
                query_id=self._query_id,
            )
            statement = await client.fetch_statement()
            report = parse_flex_report(statement.xml)
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
        except Exception as exc:
            async with db_session() as session:
                run = await session.get(SyncRun, run_id)
                if run is not None:
                    run.finished_at = datetime.now(UTC)
                    run.status = "failed"
                    run.errors = {"error": f"{type(exc).__name__}: {exc}", "trigger": trigger}
                    await session.commit()
            log.exception("flex_sync_failed", run_id=run_id)
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
                "order_id", "commission", "commission_currency", "realized_pnl_ib",
                "fx_rate_to_base", "net_amount", "order_type", "source", "updated_at",
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
                func.sum(CashTransaction.amount * func.coalesce(CashTransaction.fx_rate_to_base, 1)),
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
                "nav", "cash", "stock_value", "dividend_accruals", "interest_accruals",
                "deposits", "withdrawals", "source_line_hash", "updated_at",
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
