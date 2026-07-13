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
from app.services.live_state import _clean

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


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
