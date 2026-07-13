"""Trade journal: cycles, entries, templates, category analytics."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import (
    AuditLog,
    Instrument,
    JournalEntry,
    JournalTemplate,
    TradeCycle,
)
from app.services.trade_cycles import rebuild_cycles

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/cycles")
async def list_cycles(db: DbSession, open_only: bool = False) -> dict:
    q = (
        select(TradeCycle, Instrument)
        .join(Instrument, TradeCycle.conid == Instrument.conid)
        .order_by(desc(TradeCycle.open_time))
    )
    if open_only:
        q = q.where(TradeCycle.close_time.is_(None))
    rows = (await db.execute(q)).all()
    entries = {
        e.cycle_id: e
        for e in (await db.execute(select(JournalEntry).where(JournalEntry.cycle_id.isnot(None))))
        .scalars()
        .all()
    }
    return {
        "cycles": [
            {
                "id": c.id,
                "symbol": i.symbol,
                "name": i.name,
                "direction": c.direction,
                "open_time": c.open_time.isoformat(),
                "close_time": c.close_time.isoformat() if c.close_time else None,
                "max_quantity": str(c.max_quantity),
                "realized_pnl": str(c.realized_pnl) if c.realized_pnl is not None else None,
                "fees_total": str(c.fees_total) if c.fees_total is not None else None,
                "matching_method": c.matching_method,
                "is_manually_adjusted": c.is_manually_adjusted,
                "holding_days": (
                    ((c.close_time or datetime.now(UTC)) - c.open_time).days
                ),
                "journal": _entry_brief(entries.get(c.id)),
            }
            for c, i in rows
        ]
    }


def _entry_brief(e: JournalEntry | None) -> dict | None:
    if e is None:
        return None
    return {
        "id": e.id,
        "strategy": e.strategy,
        "rating": e.rating,
        "followed_plan": e.followed_plan,
        "key_lesson": e.key_lesson,
    }


@router.post("/cycles/rebuild")
async def rebuild(db: DbSession) -> dict:
    result = await rebuild_cycles()
    db.add(AuditLog(ts=datetime.now(UTC), actor="user", action="cycles_rebuild", details=result))
    await db.commit()
    return result


class JournalEntryIn(BaseModel):
    cycle_id: int | None = None
    strategy: str | None = Field(None, max_length=64)
    setup: str | None = Field(None, max_length=64)
    entry_reason: str | None = Field(None, max_length=8000)
    thesis: str | None = Field(None, max_length=8000)
    catalyst: str | None = Field(None, max_length=256)
    exit_reason: str | None = Field(None, max_length=8000)
    invalidation: str | None = Field(None, max_length=8000)
    target_price: Decimal | None = None
    stop_price: Decimal | None = None
    planned_rr: Decimal | None = None
    actual_rr: Decimal | None = None
    amount_at_risk: Decimal | None = None
    pct_at_risk: Decimal | None = None
    confidence: int | None = Field(None, ge=1, le=5)
    emotional_state: str | None = Field(None, max_length=64)
    followed_plan: bool | None = None
    changed_plan_midway: bool | None = None
    mistake: str | None = Field(None, max_length=8000)
    done_right: str | None = Field(None, max_length=8000)
    key_lesson: str | None = Field(None, max_length=8000)
    next_time: str | None = Field(None, max_length=8000)
    rating: int | None = Field(None, ge=1, le=5)
    free_notes: str | None = Field(None, max_length=16000)
    template_id: int | None = None
    extra_fields: dict | None = None


@router.get("/entries")
async def list_entries(db: DbSession, cycle_id: int | None = None) -> dict:
    q = select(JournalEntry).order_by(desc(JournalEntry.entry_date))
    if cycle_id is not None:
        q = q.where(JournalEntry.cycle_id == cycle_id)
    rows = (await db.execute(q)).scalars().all()
    return {"entries": [_entry_full(e) for e in rows]}


def _entry_full(e: JournalEntry) -> dict:
    return {
        c.name: (
            v.isoformat()
            if isinstance(v := getattr(e, c.name), datetime)
            else str(v)
            if isinstance(v, Decimal)
            else v
        )
        for c in JournalEntry.__table__.columns
    }


@router.post("/entries")
async def create_entry(payload: JournalEntryIn, db: DbSession) -> dict:
    now = datetime.now(UTC)
    entry = JournalEntry(entry_date=now, created_at=now, updated_at=now, **payload.model_dump())
    db.add(entry)
    db.add(AuditLog(ts=now, actor="user", action="journal_entry_create",
                    details={"cycle_id": payload.cycle_id}))
    await db.commit()
    return _entry_full(entry)


@router.put("/entries/{entry_id}")
async def update_entry(entry_id: int, payload: JournalEntryIn, db: DbSession) -> dict:
    entry = await db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(404, "journal entry not found")
    for key, value in payload.model_dump().items():
        setattr(entry, key, value)
    entry.updated_at = datetime.now(UTC)
    db.add(AuditLog(ts=entry.updated_at, actor="user", action="journal_entry_update",
                    details={"id": entry_id}))
    await db.commit()
    return _entry_full(entry)


@router.get("/templates")
async def list_templates(db: DbSession) -> dict:
    rows = (await db.execute(select(JournalTemplate))).scalars().all()
    return {
        "templates": [
            {"id": t.id, "name": t.name, "description": t.description, "fields": t.fields_schema}
            for t in rows
        ]
    }


Dimension = Literal["strategy", "setup", "symbol", "direction", "weekday", "hour", "emotional_state", "followed_plan"]


@router.get("/analytics")
async def analytics(db: DbSession, dimension: Dimension = "strategy") -> dict:
    """Aggregate CLOSED cycles by a category. Correlation, not causation —
    small buckets are flagged."""
    rows = (
        await db.execute(
            select(TradeCycle, Instrument, JournalEntry)
            .join(Instrument, TradeCycle.conid == Instrument.conid)
            .outerjoin(JournalEntry, JournalEntry.cycle_id == TradeCycle.id)
            .where(TradeCycle.close_time.isnot(None))
        )
    ).all()

    buckets: dict[str, dict] = {}
    for cycle, inst, entry in rows:
        key = _bucket_key(dimension, cycle, inst, entry)
        if key is None:
            key = "(ללא סיווג)"
        b = buckets.setdefault(
            key, {"count": 0, "wins": 0, "total_pnl": Decimal(0), "total_fees": Decimal(0)}
        )
        pnl = cycle.realized_pnl or Decimal(0)
        b["count"] += 1
        b["wins"] += 1 if pnl > 0 else 0
        b["total_pnl"] += pnl
        b["total_fees"] += cycle.fees_total or Decimal(0)

    return {
        "dimension": dimension,
        "note": "עסקאות סגורות בלבד; P&L לפני עמלות מוצג לצד סך העמלות. מתאם אינו סיבתיות.",
        "buckets": [
            {
                "key": k,
                "count": b["count"],
                "wins": b["wins"],
                "win_rate": round(b["wins"] / b["count"], 4) if b["count"] else None,
                "total_pnl": float(b["total_pnl"]),
                "avg_pnl": float(b["total_pnl"] / b["count"]) if b["count"] else None,
                "total_fees": float(b["total_fees"]),
                "small_sample": b["count"] < 10,
            }
            for k, b in sorted(buckets.items(), key=lambda kv: -kv[1]["total_pnl"])
        ],
    }


def _bucket_key(dimension: str, cycle: TradeCycle, inst: Instrument, entry: JournalEntry | None):
    if dimension == "symbol":
        return inst.symbol
    if dimension == "direction":
        return cycle.direction
    if dimension == "weekday":
        return ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"][cycle.open_time.weekday()]
    if dimension == "hour":
        return f"{cycle.open_time.hour:02d}:00"
    if entry is None:
        return None
    if dimension == "followed_plan":
        return {True: "פעל לפי התוכנית", False: "סטה מהתוכנית"}.get(entry.followed_plan)
    return getattr(entry, dimension, None)
