"""Daily OHLCV bars for instruments — cached from IBKR historical data.

Read-only: historical bars are a read request. We serve from the local cache
and only hit the gateway when a conid is missing or its latest bar is stale,
so the candlestick / sparkline charts render without pacing the gateway.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import InstrumentBar
from app.services import registry

log = get_logger(__name__)

# Refresh a conid from the gateway if we have no bars or the newest bar is older
# than this many days (covers weekends/holidays without over-fetching).
STALE_AFTER_DAYS = 2


async def _latest_dates(db: AsyncSession, conids: list[int]) -> dict[int, date]:
    if not conids:
        return {}
    rows = (
        await db.execute(
            select(InstrumentBar.conid, InstrumentBar.bar_date).where(
                InstrumentBar.conid.in_(conids)
            )
        )
    ).all()
    latest: dict[int, date] = {}
    for conid, bar_date in rows:
        if conid not in latest or bar_date > latest[conid]:
            latest[conid] = bar_date
    return latest


async def _persist(db: AsyncSession, conid: int, bars: list[dict]) -> None:
    if not bars:
        return
    now = datetime.now(UTC)
    values = [
        {
            "conid": conid,
            "bar_date": date.fromisoformat(b["date"][:10]),
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "volume": b.get("volume"),
            "source": "gateway",
            "updated_at": now,
        }
        for b in bars
    ]
    stmt = pg_insert(InstrumentBar).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_bar_conid_date",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "source": stmt.excluded.source,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def get_or_refresh_bars(
    db: AsyncSession, conids: list[int], days: int = 180
) -> dict[int, list[dict]]:
    """Return {conid: [ {date, open, high, low, close, volume}, … ]} ascending.

    Serves from the cache; refreshes stale/missing conids from the gateway when
    it is connected. Never raises on gateway problems — returns whatever is
    cached instead.
    """
    conids = [c for c in dict.fromkeys(conids)]  # de-dupe, keep order
    if not conids:
        return {}

    latest = await _latest_dates(db, conids)
    cutoff = date.today() - timedelta(days=STALE_AFTER_DAYS)
    stale = [c for c in conids if latest.get(c) is None or latest[c] < cutoff]

    gw = registry.supervisor
    if stale and gw is not None:
        # Duration a touch larger than the requested window, capped at 1Y.
        duration = "1 Y" if days > 250 else f"{max(days, 60)} D"
        for conid in stale:
            try:
                fetched = await gw.fetch_daily_bars(conid, duration=duration)
            except Exception as exc:  # never let a fetch break the response
                log.warning("bars_fetch_failed", conid=conid, error=str(exc))
                continue
            if fetched:
                await _persist(db, conid, fetched)

    since = date.today() - timedelta(days=days)
    rows = (
        await db.execute(
            select(InstrumentBar)
            .where(InstrumentBar.conid.in_(conids), InstrumentBar.bar_date >= since)
            .order_by(InstrumentBar.conid, InstrumentBar.bar_date)
        )
    ).scalars().all()

    out: dict[int, list[dict]] = {c: [] for c in conids}
    for r in rows:
        out[r.conid].append(
            {
                "date": r.bar_date.isoformat(),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume) if r.volume is not None else None,
            }
        )
    return out
