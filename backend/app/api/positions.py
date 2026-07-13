"""Open positions — live when connected, last persisted otherwise."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Instrument, Position
from app.ibkr.types import GatewayState
from app.services import registry
from app.services.bars import get_or_refresh_bars
from app.services.live_state import _clean

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _open_instruments(db: AsyncSession) -> list[tuple[int, str, str | None]]:
    """(conid, symbol, name) for every open position (tradable secs only)."""
    rows = (
        await db.execute(
            select(Instrument.conid, Instrument.symbol, Instrument.name)
            .join(Position, Position.conid == Instrument.conid)
            .where(Position.is_open.is_(True), Instrument.sec_type != "CASH")
        )
    ).all()
    return [(c, s, n) for c, s, n in rows]


@router.get("")
async def list_positions(db: DbSession) -> dict:
    live = registry.live_state
    if live and live.positions and live.connection.state == GatewayState.CONNECTED:
        return {
            "source": "ibkr_gateway",
            "stale": False,
            "positions": [
                _clean(asdict(p)) for p in live.positions.values() if p.quantity != 0
            ],
        }

    rows = (
        await db.execute(
            select(Position, Instrument)
            .join(Instrument, Position.conid == Instrument.conid)
            .where(Position.is_open.is_(True))
        )
    ).all()
    return {
        "source": "local_snapshot" if rows else None,
        "stale": True,
        "positions": [
            {
                "ts": p.updated_at.isoformat(),
                "instrument": {
                    "conid": i.conid,
                    "symbol": i.symbol,
                    "sec_type": i.sec_type,
                    "currency": i.currency,
                    "name": i.name,
                    "exchange": i.exchange,
                },
                "quantity": str(p.quantity),
                "avg_cost": str(p.avg_cost) if p.avg_cost is not None else None,
                "market_price": str(p.market_price) if p.market_price is not None else None,
                "market_value": str(p.market_value) if p.market_value is not None else None,
                "unrealized_pnl": str(p.unrealized_pnl) if p.unrealized_pnl is not None else None,
                "daily_pnl": str(p.daily_pnl) if p.daily_pnl is not None else None,
                "price_quality": p.price_quality,
            }
            for p, i in rows
        ],
    }


@router.get("/bars")
async def positions_bars(db: DbSession, days: int = 180) -> dict:
    """Daily OHLCV series for every open position — drives the dashboard
    candlestick and the positions sparklines. Served from cache; refreshed
    from the gateway (read-only) when stale."""
    instruments = await _open_instruments(db)
    conids = [c for c, _, _ in instruments]
    series = await get_or_refresh_bars(db, conids, days=days)
    labels = {c: (s, n) for c, s, n in instruments}
    out = {
        str(conid): {
            "symbol": labels[conid][0],
            "name": labels[conid][1],
            "bars": bars,
        }
        for conid, bars in series.items()
    }
    return {"available": any(v["bars"] for v in out.values()), "series": out}


@router.get("/{conid}/bars")
async def instrument_bars(conid: int, db: DbSession, days: int = 180) -> dict:
    """Daily OHLCV series for a single instrument (asset page candlestick)."""
    series = await get_or_refresh_bars(db, [conid], days=days)
    bars = series.get(conid, [])
    return {"available": bool(bars), "conid": conid, "bars": bars}
