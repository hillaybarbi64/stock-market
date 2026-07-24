"""Trade-cycle builder: groups executions into round trips (FIFO).

A cycle opens when the position leaves zero and closes when it returns to
zero. A fill that crosses zero (e.g. long 5 → sell 8) is split: 5 shares
close the long cycle, 3 open a new short cycle.

Realized P&L is computed from our own FIFO lots (documented, reproducible)
and kept alongside the sum IBKR reports per execution — the two are compared
in reconciliation, never silently merged.

Cycles carry a stable natural key (conid, opening execution id) so journal
entries survive rebuilds even when multiple cycles open in the same second.
Manually adjusted cycles are never touched by a rebuild.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import (
    Attachment,
    CycleExecution,
    EntityTag,
    Execution,
    JournalEntry,
    TradeCycle,
)

log = get_logger(__name__)
_CYCLE_ENTITY_TYPES = ("cycle", "trade_cycle")


@dataclass
class _Lot:
    quantity: Decimal
    price: Decimal


@dataclass
class _OpenCycle:
    conid: int
    direction: str  # LONG | SHORT
    open_time: datetime
    open_exec_id: str
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
    open_exec_id: str
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
                current = _OpenCycle(
                    conid=ex.conid,
                    direction=direction,
                    open_time=ex.trade_time,
                    open_exec_id=ex.exec_id,
                )

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
                        ex.price - lot.price
                        if current.direction == "LONG"
                        else lot.price - ex.price
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
        open_exec_id=c.open_exec_id,
        close_time=c.close_time,
        max_quantity=c.max_qty,
        realized_pnl=c.realized,
        realized_pnl_ib=c.realized_ib,
        fees_total=c.fees,
        allocations=c.allocations,
    )


def _plan_stale_cycle_replacements(
    stale_cycles: dict[int, str],
    cycle_ids_by_exec: dict[str, set[int]],
) -> dict[int, int]:
    """Map a stale cycle to the one unambiguous new cycle containing its opener."""
    replacements: dict[int, int] = {}
    for stale_id, open_exec_id in stale_cycles.items():
        candidates = cycle_ids_by_exec.get(open_exec_id, set())
        if len(candidates) != 1:
            continue
        replacement_id = next(iter(candidates))
        if replacement_id != stale_id:
            replacements[stale_id] = replacement_id
    return replacements


async def _reassign_cycle_references(
    session: AsyncSession,
    source_cycle_id: int,
    target_cycle_id: int,
) -> None:
    """Move user-owned references, deduplicating polymorphic tags safely."""
    await session.execute(
        update(JournalEntry)
        .where(JournalEntry.cycle_id == source_cycle_id)
        .values(cycle_id=target_cycle_id)
    )

    source_entity_id = str(source_cycle_id)
    target_entity_id = str(target_cycle_id)
    target_tag_keys = set(
        (
            await session.execute(
                select(EntityTag.tag_id, EntityTag.entity_type).where(
                    EntityTag.entity_type.in_(_CYCLE_ENTITY_TYPES),
                    EntityTag.entity_id == target_entity_id,
                )
            )
        ).all()
    )
    source_tags = (
        (
            await session.execute(
                select(EntityTag).where(
                    EntityTag.entity_type.in_(_CYCLE_ENTITY_TYPES),
                    EntityTag.entity_id == source_entity_id,
                )
            )
        )
        .scalars()
        .all()
    )
    for tag in source_tags:
        key = (tag.tag_id, tag.entity_type)
        if key in target_tag_keys:
            await session.delete(tag)
            continue
        tag.entity_id = target_entity_id
        target_tag_keys.add(key)

    await session.execute(
        update(Attachment)
        .where(
            Attachment.entity_type.in_(_CYCLE_ENTITY_TYPES),
            Attachment.entity_id == source_entity_id,
        )
        .values(entity_id=target_entity_id)
    )
    await session.flush()


async def _referenced_cycle_ids(
    session: AsyncSession,
    cycle_ids: set[int],
) -> set[int]:
    """Return stale IDs that still own journal, tag, or attachment data."""
    if not cycle_ids:
        return set()

    referenced = set(
        (
            await session.execute(
                select(JournalEntry.cycle_id).where(JournalEntry.cycle_id.in_(cycle_ids)).distinct()
            )
        )
        .scalars()
        .all()
    )
    entity_to_cycle_id = {str(cycle_id): cycle_id for cycle_id in cycle_ids}
    entity_ids = set(entity_to_cycle_id)
    for model in (EntityTag, Attachment):
        rows = (
            (
                await session.execute(
                    select(model.entity_id)
                    .where(
                        model.entity_type.in_(_CYCLE_ENTITY_TYPES),
                        model.entity_id.in_(entity_ids),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        referenced.update(entity_to_cycle_id[entity_id] for entity_id in rows)
    return referenced


async def _reconcile_stale_cycles(
    session: AsyncSession,
    stale_cycles: dict[int, str],
    cycle_ids_by_exec: dict[str, set[int]],
) -> tuple[set[int], int, set[int]]:
    """Move references where safe and identify stale rows that may be deleted.

    A referenced stale cycle is retained when its old opening execution is not
    contained by exactly one rebuilt cycle. Preserving an obsolete row is safer
    than silently orphaning user-authored journal data or files.
    """
    replacements = _plan_stale_cycle_replacements(stale_cycles, cycle_ids_by_exec)
    for source_cycle_id, target_cycle_id in replacements.items():
        await _reassign_cycle_references(session, source_cycle_id, target_cycle_id)

    without_replacement = set(stale_cycles).difference(replacements)
    preserved = await _referenced_cycle_ids(session, without_replacement)
    deletable = set(stale_cycles).difference(preserved)
    return deletable, len(replacements), preserved


async def rebuild_cycles() -> dict[str, int]:
    """Rebuild auto-matched cycles from all executions. Manually adjusted
    cycles (and their instruments) are left untouched. If newly imported
    history changes a cycle's opening execution, user-owned references move to
    the rebuilt cycle containing the old opener."""
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
            (
                await session.execute(
                    select(Execution).order_by(
                        Execution.trade_time,
                        Execution.exec_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        by_conid: dict[int, list[Execution]] = {}
        for ex in executions:
            if ex.conid not in manual_conids:
                by_conid.setdefault(ex.conid, []).append(ex)

        built = 0
        references_reassigned = 0
        stale_preserved = 0
        for conid, exs in by_conid.items():
            cycles = build_cycles(exs)
            # replace previous auto allocations for this instrument
            old_cycles = dict(
                (
                    await session.execute(
                        select(TradeCycle.id, TradeCycle.open_exec_id).where(
                            TradeCycle.conid == conid,
                            TradeCycle.is_manually_adjusted.is_(False),
                        )
                    )
                ).all()
            )
            stale = set(old_cycles)
            cycle_ids_by_exec: dict[str, set[int]] = {}
            for c in cycles:
                stmt = pg_insert(TradeCycle).values(
                    conid=c.conid,
                    open_exec_id=c.open_exec_id,
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
                    constraint="uq_cycle_conid_open_exec",
                    set_={
                        col: getattr(stmt.excluded, col)
                        for col in (
                            "direction",
                            "close_time",
                            "max_quantity",
                            "realized_pnl",
                            "fees_total",
                            "original_matching",
                            "updated_at",
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
                    cycle_ids_by_exec.setdefault(exec_id, set()).add(cycle_id)
                built += 1
            if stale:
                deletable, reassigned, preserved = await _reconcile_stale_cycles(
                    session,
                    {cycle_id: old_cycles[cycle_id] for cycle_id in stale},
                    cycle_ids_by_exec,
                )
                references_reassigned += reassigned
                stale_preserved += len(preserved)
                if preserved:
                    log.warning(
                        "referenced_stale_cycles_preserved",
                        conid=conid,
                        cycle_ids=sorted(preserved),
                    )
                if deletable:
                    await session.execute(delete(TradeCycle).where(TradeCycle.id.in_(deletable)))
        await session.commit()
    log.info(
        "cycles_rebuilt",
        cycles=built,
        manual_skipped=len(manual_conids),
        references_reassigned=references_reassigned,
        stale_preserved=stale_preserved,
    )
    return {"cycles": built, "manual_instruments_skipped": len(manual_conids)}
