"""Sync ingestion: idempotency, flow aggregation into daily equity,
gateway→flex enrichment precedence. Runs against real PostgreSQL."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.db.base import db_session, dispose_engine
from app.db.models import (
    CashTransaction,
    CorporateAction,
    DailyEquity,
    Execution,
    FxRate,
    Instrument,
)
from app.ibkr.flex_parser import parse_flex_report
from app.services.flex_sync import FlexSyncService

FIXTURE = (Path(__file__).parent / "fixtures" / "activity_flex_sample.xml").read_text()
FIXTURE_CONIDS = (431495220, 266143774)


async def _cleanup():
    async with db_session() as s:
        await s.execute(delete(Execution).where(Execution.conid.in_(FIXTURE_CONIDS)))
        await s.execute(delete(CashTransaction))
        await s.execute(delete(CorporateAction))
        await s.execute(delete(DailyEquity))
        await s.execute(delete(FxRate))
        from app.db.models import Position

        await s.execute(delete(Position).where(Position.conid.in_(FIXTURE_CONIDS)))
        await s.execute(delete(Instrument).where(Instrument.conid.in_(FIXTURE_CONIDS)))
        await s.commit()


def make_service() -> FlexSyncService:
    return FlexSyncService(Settings(ibkr_gateway_autostart=False, _env_file=None))


async def test_ingest_twice_is_idempotent():
    await _cleanup()
    service = make_service()
    report = parse_flex_report(FIXTURE)
    try:
        first = await service.ingest(report)
        assert first["upserted"] > 0

        second = await service.ingest(report)
        # corporate actions/fx are unconditional upserts; the row-counts that
        # matter (executions, cash, equity) must all be unchanged.
        async with db_session() as s:
            execs = (await s.execute(select(func.count()).select_from(Execution))).scalar_one()
            cash = (await s.execute(select(func.count()).select_from(CashTransaction))).scalar_one()
            days = (await s.execute(select(func.count()).select_from(DailyEquity))).scalar_one()
        assert execs == 3
        assert cash == 4
        assert days == 3
        assert second["unchanged"] >= 10  # 3 trades + 4 cash + 3 equity days
    finally:
        await _cleanup()
        await dispose_engine()


async def test_deposit_lands_in_daily_equity_in_base_currency():
    await _cleanup()
    service = make_service()
    try:
        await service.ingest(parse_flex_report(FIXTURE))
        async with db_session() as s:
            day = await s.get(DailyEquity, date(2026, 2, 17))
        assert day is not None
        # ILS 10,000 * 0.30078 = 3,007.80 in base (USD)
        assert day.deposits == Decimal("3007.8000")
        assert day.withdrawals == 0
    finally:
        await _cleanup()
        await dispose_engine()


async def test_flex_enriches_gateway_execution():
    """A fill first seen live (gateway, no exact commission) must be upgraded
    by the flex row — same exec_id, richer data, still one row."""
    await _cleanup()
    service = make_service()
    try:
        from datetime import UTC, datetime

        from app.ibkr.types import ExecutionData, InstrumentData
        from app.services.live_state import LiveStateService
        from app.ws.hub import WsHub

        live = LiveStateService(WsHub(min_interval_s=0))
        await live.on_execution(
            ExecutionData(
                exec_id="00030f00.6a30db78.01.01",
                instrument=InstrumentData(431495220, "SNEX", "STK", "USD"),
                side="BUY",
                quantity=Decimal("8"),
                price=Decimal("137.385"),
                trade_time=datetime(2026, 6, 15, 16, 19, 32, tzinfo=UTC),
            )
        )
        await service.ingest(parse_flex_report(FIXTURE))
        async with db_session() as s:
            row = await s.get(Execution, "00030f00.6a30db78.01.01")
        assert row is not None
        assert row.source == "flex"
        assert row.commission == Decimal("-1")
        assert row.realized_pnl_ib == Decimal("0")
    finally:
        await _cleanup()
        await dispose_engine()
