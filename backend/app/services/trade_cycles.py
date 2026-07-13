"""Trade-cycle builder: groups executions into round trips (FIFO).

A cycle opens when the position leaves zero and closes when it returns to
zero. A fill that crosses zero (e.g. long 5 → sell 8) is split: 5 shares
close the long cycle, 3 open a new short cycle.

Realized P&L is computed from our own FIFO lots (documented, reproducible)
and kept alongside the sum IBKR reports per execution — the two are compared
in reconciliation, never silently merged.

Cycles carry a stable natural key (conid, open_time) so journal entries
survive rebuilds. Manually adjusted cycles are never touched by a rebuild.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import CycleExecution, Execution, TradeCycle

log = get_logger(__name__)


@dataclass
class _Lot:
    quantity: Decimal
    price: Decimal


@dataclass
class _OpenCycle:
    conid: int
    direction: str  # LONG | SHORT
    open_time: datetime
    lots: list[_Lot] = field(default_factory=list)
    allocations: list[tuple[str, Decimal]] = field(default_factory=list)  # (exec_id, qty)
    realized: Decimal = Decimal(0)
    realized_ib: Decimal = Decimal(0)
    fees: Decimal = Decimal(0)
    max_qty: Decimal = Decimal(0)
    close_time: datetime | None = None


@dataclass(frozen=True)
class CycleResult:
    conid: int
    direction: str
    open_time: datetime
    close_time: datetime | None
    max_quantity: Decimal
    realized_pnl: Decimal
    realized_pnl_ib: Decimal
    fees_total: Decimal
    allocations: list[tuple[str, Decimal]]


def build_cycles(executions: list[Execution]) -> list[CycleResult]:
    """Pure FIFO cycle construction from executions of a single instrument,
    ordered by trade_time."""
    results: list[CycleResult] = []
    current: _OpenCycle | None = None
    position = Decimal(0)

    for ex in executions:
        remaining = ex.quantity if ex.side == "BUY" else -ex.quantity
        fee = abs(ex.commission or 0)
        fee_charged = False

        while remaining != 0:
            if current is None:
                direction = "LONG" if remaining > 0 else "SHORT"
                current = _OpenCycle(conid=ex.conid, direction=direction, open_time=ex.trade_time)

            same_direction = (current.direction == "LONG") == (remaining > 0)
            if same_direction:
                current.lots.append(_Lot(quantity=abs(remaining), price=ex.price))
                current.allocations.append((ex.exec_id, abs(remaining)))
                if not fee_charged:
                    current.fees += fee
                    fee_charged = True
                position += remaining
                current.max_qty = max(current.max_qty, abs(position))
                remaining = Decimal(0)
            else:
                # closing (possibly partially, possibly crossing zero)
                close_qty = min(abs(remaining), abs(position))
                current.allocations.append((ex.exec_id, close_qty))
                if not fee_charged:
                    current.fees += fee
                    fee_charged = True
                if ex.realized_pnl_ib is not None:
                    current.realized_ib += ex.realized_pnl_ib
                qty_left = close_qty
                while qty_left > 0 and current.lots:
                    lot = current.lots[0]
                    used = min(lot.quantity, qty_left)
                    pnl_per_share = (
                        ex.price - lot.price if current.direction == "LONG" else lot.price - ex.price
                    )
                    current.realized += pnl_per_share * used
                    lot.quantity -= used
                    qty_left -= used
                    if lot.quantity == 0:
                        current.lots.pop(0)
                position += close_qty if remaining > 0 else -close_qty
                remaining -= close_qty if remaining > 0 else -close_qty
                if position == 0:
                    current.close_time = ex.trade_time
                    results.append(_finish(current))
                    current = None

    if current is not None:
        results.append(_finish(current))
    return results


def _finish(c: _OpenCycle) -> CycleResult:
    return CycleResult(
        conid=c.conid,
        direction=c.direction,
        open_time=c.open_time,
        close_time=c.close_time,
        max_quantity=c.max_qty,
        realized_pnl=c.realized,
        realized_pnl_ib=c.realized_ib,
        fees_total=c.fees,
        allocations=c.allocations,
    )


async def rebuild_cycles() -> dict[str, int]:
    """Rebuild auto-matched cycles from all executions. Manually adjusted
    cycles (and their instruments) are left untouched. Journal entries keep
    pointing at the same cycle rows thanks to the (conid, open_time) upsert."""
    async with db_session() as session:
        manual_conids = set(
            (
                await session.execute(
                    select(TradeCycle.conid).where(TradeCycle.is_manually_adjusted.is_(True))
                )
            )
            .scalars()
            .all()
        )
        executions = (
            (await session.execute(select(Execution).order_by(Execution.trade_time)))
            .scalars()
            .all()
        )
        by_conid: dict[int, list[Execution]] = {}
        for ex in executions:
            if ex.conid not in manual_conids:
                by_conid.setdefault(ex.conid, []).append(ex)

        built = 0
        for conid, exs in by_conid.items():
            cycles = build_cycles(exs)
            # replace previous auto allocations for this instrument
            old_ids = (
                (
                    await session.execute(
                        select(TradeCycle.id).where(
                            TradeCycle.conid == conid,
                            TradeCycle.is_manually_adjusted.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
            stale = set(old_ids)
            for c in cycles:
                stmt = pg_insert(TradeCycle).values(
                    conid=c.conid,
                    direction=c.direction,
                    open_time=c.open_time,
                    close_time=c.close_time,
                    max_quantity=c.max_quantity,
                    realized_pnl=c.realized_pnl,
                    fees_total=c.fees_total,
                    matching_method="FIFO",
                    is_manually_adjusted=False,
                    original_matching={
                        "allocations": [[e, str(q)] for e, q in c.allocations],
                        "realized_pnl_ib": str(c.realized_pnl_ib),
                    },
                    updated_at=datetime.now(UTC),
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_cycle_conid_open",
                    set_={
                        col: getattr(stmt.excluded, col)
                        for col in (
                            "direction", "close_time", "max_quantity", "realized_pnl",
                            "fees_total", "original_matching", "updated_at",
                        )
                    },
                ).returning(TradeCycle.id)
                cycle_id = (await session.execute(stmt)).scalar_one()
                stale.discard(cycle_id)
                await session.execute(
                    delete(CycleExecution).where(CycleExecution.cycle_id == cycle_id)
                )
                for exec_id, qty in c.allocations:
                    session.add(
                        CycleExecution(cycle_id=cycle_id, exec_id=exec_id, allocated_quantity=qty)
                    )
                built += 1
            if stale:
                await session.execute(delete(TradeCycle).where(TradeCycle.id.in_(stale)))
        await session.commit()
    log.info("cycles_rebuilt", cycles=built, manual_skipped=len(manual_conids))
    return {"cycles": built, "manual_instruments_skipped": len(manual_conids)}
