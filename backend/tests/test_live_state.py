"""LiveStateService: memory + hub fan-out + idempotent persistence (real PG)."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.db.base import db_session, dispose_engine
from app.db.models import Execution, Instrument, Position
from app.ibkr.types import ExecutionData, InstrumentData, PositionData, PriceQuality
from app.services.live_state import LiveStateService
from app.ws.hub import WsHub

INST = InstrumentData(conid=431495220, symbol="SNEX", sec_type="STK", currency="USD")


def make_position(qty="8", price="117.18") -> PositionData:
    return PositionData(
        ts=datetime.now(UTC),
        instrument=INST,
        quantity=Decimal(qty),
        avg_cost=Decimal("137.6975"),
        market_price=Decimal(price),
        market_value=Decimal(price) * Decimal(qty),
        unrealized_pnl=Decimal("-164.14"),
        price_quality=PriceQuality.DELAYED,
    )


def make_execution(exec_id="0001.test.01") -> ExecutionData:
    return ExecutionData(
        exec_id=exec_id,
        instrument=INST,
        side="BUY",
        quantity=Decimal("8"),
        price=Decimal("137.385"),
        trade_time=datetime(2026, 6, 15, 16, 19, 32, tzinfo=UTC),
        commission=Decimal("2.5"),
        commission_currency="USD",
    )


async def _cleanup():
    async with db_session() as s:
        await s.execute(delete(Execution).where(Execution.conid == INST.conid))
        await s.execute(delete(Position).where(Position.conid == INST.conid))
        await s.execute(delete(Instrument).where(Instrument.conid == INST.conid))
        await s.commit()


async def test_position_updates_memory_and_persists():
    service = LiveStateService(WsHub(min_interval_s=0))
    try:
        await service.on_position(make_position())
        assert service.positions[INST.conid].quantity == Decimal("8")

        # update with new price — same row, not a duplicate
        await service.on_position(make_position(price="118.00"))
        async with db_session() as s:
            count = (
                await s.execute(
                    select(func.count()).select_from(Position).where(Position.conid == INST.conid)
                )
            ).scalar_one()
            row = (
                await s.execute(select(Position).where(Position.conid == INST.conid))
            ).scalar_one()
        assert count == 1
        assert row.market_price == Decimal("118.00")
        assert row.price_quality == "delayed"
    finally:
        await _cleanup()
        await dispose_engine()


async def test_execution_persistence_is_idempotent():
    service = LiveStateService(WsHub(min_interval_s=0))
    try:
        await service.on_execution(make_execution())
        await service.on_execution(make_execution())  # same exec_id again
        async with db_session() as s:
            count = (
                await s.execute(
                    select(func.count()).select_from(Execution).where(Execution.conid == INST.conid)
                )
            ).scalar_one()
        assert count == 1, "repeated execution events must never duplicate"
    finally:
        await _cleanup()
        await dispose_engine()
