"""Account summary & balances.

Serves the live in-memory state when connected; when not connected, falls
back to the most recent persisted snapshot and says so (`stale: true`,
`as_of` timestamp) — old data is never presented as fresh.
"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import AccountSnapshot, CashBalance
from app.ibkr.types import GatewayState
from app.services import registry
from app.services.live_state import _clean

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary")
async def account_summary(db: DbSession) -> dict:
    live = registry.live_state
    if live and live.account and live.connection.state == GatewayState.CONNECTED:
        return {
            "source": "ibkr_gateway",
            "stale": False,
            "as_of": live.account.ts.isoformat(),
            "data": _clean(asdict(live.account)),
        }

    row = (
        await db.execute(select(AccountSnapshot).order_by(desc(AccountSnapshot.ts)).limit(1))
    ).scalar_one_or_none()
    if row is None:
        return {"source": None, "stale": True, "as_of": None, "data": None}
    return {
        "source": "local_snapshot",
        "stale": True,
        "as_of": row.ts.isoformat(),
        "data": {
            "base_currency": row.base_currency,
            "net_liquidation": str(row.net_liquidation),
            "total_cash": str(row.total_cash) if row.total_cash is not None else None,
            "gross_position_value": str(row.gross_position_value)
            if row.gross_position_value is not None
            else None,
            "buying_power": str(row.buying_power) if row.buying_power is not None else None,
            "available_funds": str(row.available_funds) if row.available_funds is not None else None,
            "excess_liquidity": str(row.excess_liquidity) if row.excess_liquidity is not None else None,
            "init_margin": str(row.init_margin) if row.init_margin is not None else None,
            "maint_margin": str(row.maint_margin) if row.maint_margin is not None else None,
            "unrealized_pnl": str(row.unrealized_pnl) if row.unrealized_pnl is not None else None,
            "realized_pnl": str(row.realized_pnl) if row.realized_pnl is not None else None,
            "leverage": str(row.leverage) if row.leverage is not None else None,
        },
    }


@router.get("/balances")
async def cash_balances(db: DbSession) -> dict:
    live = registry.live_state
    if live and live.balances and live.connection.state == GatewayState.CONNECTED:
        return {
            "source": "ibkr_gateway",
            "stale": False,
            "balances": [_clean(asdict(b)) for b in live.balances],
        }
    latest_ts = (
        await db.execute(select(CashBalance.ts).order_by(desc(CashBalance.ts)).limit(1))
    ).scalar_one_or_none()
    if latest_ts is None:
        return {"source": None, "stale": True, "balances": []}
    rows = (
        (await db.execute(select(CashBalance).where(CashBalance.ts == latest_ts))).scalars().all()
    )
    return {
        "source": "local_snapshot",
        "stale": True,
        "balances": [
            {
                "ts": r.ts.isoformat(),
                "currency": r.currency,
                "cash_balance": str(r.cash_balance),
                "settled_cash": str(r.settled_cash) if r.settled_cash is not None else None,
                "nlv_in_ccy": str(r.nlv_in_ccy) if r.nlv_in_ccy is not None else None,
                "fx_rate_to_base": str(r.fx_rate_to_base) if r.fx_rate_to_base is not None else None,
            }
            for r in rows
        ],
    }
