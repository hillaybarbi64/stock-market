"""Reference preservation for trade-cycle rebuilds; runs on in-memory SQLite."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
from app.db.models import (
    Attachment,
    EntityTag,
    Instrument,
    JournalEntry,
    JournalTemplate,
    Tag,
    TradeCycle,
)
from app.services.trade_cycles import (
    _plan_stale_cycle_replacements,
    _reconcile_stale_cycles,
)


def test_stale_replacement_requires_one_distinct_cycle_containing_the_old_opener():
    assert _plan_stale_cycle_replacements(
        {
            1: "unique",
            2: "missing",
            3: "ambiguous",
            4: "same-row",
        },
        {
            "unique": {10},
            "ambiguous": {10, 11},
            "same-row": {4},
        },
    ) == {1: 10}


async def test_reconcile_moves_all_references_dedupes_tags_and_preserves_unmapped():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Instrument.__table__,
        JournalTemplate.__table__,
        Tag.__table__,
        TradeCycle.__table__,
        JournalEntry.__table__,
        EntityTag.__table__,
        Attachment.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=tables,
            )
        )

    now = datetime(2026, 7, 24, tzinfo=UTC)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(
                Instrument(
                    conid=991_000_001,
                    symbol="TEST",
                    sec_type="STK",
                    currency="USD",
                    updated_at=now,
                )
            )
            cycles = [
                TradeCycle(
                    conid=991_000_001,
                    open_exec_id=open_exec_id,
                    direction="LONG",
                    open_time=now,
                    max_quantity=Decimal("1"),
                    matching_method="FIFO",
                    is_manually_adjusted=False,
                    updated_at=now,
                )
                for open_exec_id in (
                    "old-open",
                    "early-open",
                    "missing-open",
                    "unused-open",
                )
            ]
            source, target, preserved_cycle, unreferenced_cycle = cycles
            session.add_all(cycles)
            duplicate_tag = Tag(name="duplicate", color="#00ff00")
            movable_tag = Tag(name="movable", color="#ffffff")
            session.add_all([duplicate_tag, movable_tag])
            await session.flush()

            session.add(
                JournalEntry(
                    cycle_id=source.id,
                    entry_date=now,
                    free_notes="keep me",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add_all(
                [
                    EntityTag(
                        tag_id=duplicate_tag.id,
                        entity_type="cycle",
                        entity_id=str(target.id),
                    ),
                    EntityTag(
                        tag_id=duplicate_tag.id,
                        entity_type="cycle",
                        entity_id=str(source.id),
                    ),
                    EntityTag(
                        tag_id=movable_tag.id,
                        entity_type="cycle",
                        entity_id=str(source.id),
                    ),
                ]
            )
            session.add_all(
                [
                    Attachment(
                        entity_type="cycle",
                        entity_id=str(source.id),
                        file_path="/data/source.png",
                        uploaded_at=now,
                    ),
                    Attachment(
                        entity_type="cycle",
                        entity_id=str(preserved_cycle.id),
                        file_path="/data/preserved.png",
                        uploaded_at=now,
                    ),
                ]
            )
            await session.flush()

            deletable, reassigned, preserved = await _reconcile_stale_cycles(
                session,
                {
                    source.id: source.open_exec_id,
                    preserved_cycle.id: preserved_cycle.open_exec_id,
                    unreferenced_cycle.id: unreferenced_cycle.open_exec_id,
                },
                {source.open_exec_id: {target.id}},
            )

            assert reassigned == 1
            assert preserved == {preserved_cycle.id}
            assert deletable == {source.id, unreferenced_cycle.id}

            journal_cycle_ids = set(
                (await session.execute(select(JournalEntry.cycle_id))).scalars().all()
            )
            assert journal_cycle_ids == {target.id}

            target_tags = (
                (
                    await session.execute(
                        select(EntityTag).where(
                            EntityTag.entity_type == "cycle",
                            EntityTag.entity_id == str(target.id),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert {(tag.tag_id, tag.entity_type) for tag in target_tags} == {
                (duplicate_tag.id, "cycle"),
                (movable_tag.id, "cycle"),
            }
            assert not (
                await session.execute(
                    select(EntityTag.id).where(EntityTag.entity_id == str(source.id))
                )
            ).first()

            attachment_entities = set(
                (await session.execute(select(Attachment.entity_id))).scalars().all()
            )
            assert attachment_entities == {str(target.id), str(preserved_cycle.id)}

            await session.execute(delete(TradeCycle).where(TradeCycle.id.in_(deletable)))
            await session.flush()
            assert await session.get(TradeCycle, preserved_cycle.id) is not None
    finally:
        await engine.dispose()
