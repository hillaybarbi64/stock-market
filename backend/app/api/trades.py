"""Executed trades (fills) with filtering and pagination."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Execution, Instrument

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("")
async def list_trades(
    db: DbSession,
    symbol: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(le=500)] = 100,
    offset: int = 0,
) -> dict:
    conditions = []
    if symbol:
        conditions.append(Instrument.symbol.ilike(f"%{symbol}%"))
    if date_from:
        conditions.append(func.date(Execution.trade_time) >= date_from)
    if date_to:
        conditions.append(func.date(Execution.trade_time) <= date_to)

    base = select(Execution, Instrument).join(Instrument, Execution.conid == Instrument.conid)
    if conditions:
        base = base.where(*conditions)

    total = (
        await db.execute(
            select(func.count())
            .select_from(Execution)
            .join(Instrument, Execution.conid == Instrument.conid)
            .where(*conditions)
        )
    ).scalar_one()
    rows = (
        await db.execute(base.order_by(desc(Execution.trade_time)).limit(limit).offset(offset))
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "trades": [
            {
                "exec_id": e.exec_id,
                "order_id": e.order_id,
                "symbol": i.symbol,
                "name": i.name,
                "sec_type": i.sec_type,
                "side": e.side,
                "quantity": str(e.quantity),
                "price": str(e.price),
                "trade_time": e.trade_time.isoformat(),
                "exchange": e.exchange,
                "order_type": e.order_type,
                "commission": str(e.commission) if e.commission is not None else None,
                "commission_currency": e.commission_currency,
                "realized_pnl_ib": str(e.realized_pnl_ib) if e.realized_pnl_ib is not None else None,
                "currency": e.currency,
                "net_amount": str(e.net_amount) if e.net_amount is not None else None,
                "source": e.source,
            }
            for e, i in rows
        ],
    }
