"""Exports (CSV) and periodic report data.

CSV is streamed server-side (Excel-compatible, UTF-8 BOM). The periodic
report returns structured JSON; the frontend renders it print-friendly so
the browser's Save-as-PDF produces the document — no extra PDF stack.
"""

import csv
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.performance import _load_points
from app.db.base import get_db
from app.db.models import CashTransaction, DailyEquity, Execution, Instrument, TradeCycle
from app.services.performance import chain_returns, daily_returns, drawdown, total_twr

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _csv_response(name: str, header: list[str], rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens UTF-8 (Hebrew) correctly
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/export/trades.csv")
async def export_trades(db: DbSession) -> StreamingResponse:
    rows = (
        await db.execute(
            select(Execution, Instrument)
            .join(Instrument, Execution.conid == Instrument.conid)
            .order_by(Execution.trade_time)
        )
    ).all()
    return _csv_response(
        "trades.csv",
        ["exec_id", "symbol", "side", "quantity", "price", "trade_time", "exchange",
         "order_type", "commission", "commission_ccy", "realized_pnl_ib", "currency",
         "fx_rate_to_base", "net_amount", "source"],
        [
            [e.exec_id, i.symbol, e.side, e.quantity, e.price, e.trade_time.isoformat(),
             e.exchange, e.order_type, e.commission, e.commission_currency,
             e.realized_pnl_ib, e.currency, e.fx_rate_to_base, e.net_amount, e.source]
            for e, i in rows
        ],
    )


@router.get("/export/cycles.csv")
async def export_cycles(db: DbSession) -> StreamingResponse:
    rows = (
        await db.execute(
            select(TradeCycle, Instrument)
            .join(Instrument, TradeCycle.conid == Instrument.conid)
            .order_by(TradeCycle.open_time)
        )
    ).all()
    return _csv_response(
        "trade_cycles.csv",
        ["id", "symbol", "direction", "open_time", "close_time", "max_quantity",
         "realized_pnl", "fees_total", "matching_method", "manually_adjusted"],
        [
            [c.id, i.symbol, c.direction, c.open_time.isoformat(),
             c.close_time.isoformat() if c.close_time else "", c.max_quantity,
             c.realized_pnl, c.fees_total, c.matching_method, c.is_manually_adjusted]
            for c, i in rows
        ],
    )


@router.get("/export/daily_equity.csv")
async def export_daily_equity(db: DbSession) -> StreamingResponse:
    rows = (
        (await db.execute(select(DailyEquity).order_by(DailyEquity.equity_date))).scalars().all()
    )
    return _csv_response(
        "daily_equity.csv",
        ["date", "nav", "cash", "stock_value", "deposits", "withdrawals"],
        [[r.equity_date, r.nav, r.cash, r.stock_value, r.deposits, r.withdrawals] for r in rows],
    )


@router.get("/periodic")
async def periodic_report(db: DbSession, date_from: date, date_to: date) -> dict:
    """Data for a periodic report over [date_from, date_to]."""
    points = [p for p in await _load_points(db) if date_from <= p.day <= date_to]
    if len(points) < 2:
        return {"available": False, "detail": "אין מספיק ימי נתונים מסונכרנים בטווח שנבחר"}

    returns = daily_returns(points)
    dd = drawdown(chain_returns(returns))

    cash_rows = (
        await db.execute(
            select(
                CashTransaction.type,
                func.sum(CashTransaction.amount * func.coalesce(CashTransaction.fx_rate_to_base, 1)),
            )
            .where(
                func.date(CashTransaction.tx_datetime) >= date_from,
                func.date(CashTransaction.tx_datetime) <= date_to,
            )
            .group_by(CashTransaction.type)
        )
    ).all()
    cash = {t: float(v) for t, v in cash_rows}

    trades_count = (
        await db.execute(
            select(func.count())
            .select_from(Execution)
            .where(
                func.date(Execution.trade_time) >= date_from,
                func.date(Execution.trade_time) <= date_to,
            )
        )
    ).scalar_one()

    cycles = (
        await db.execute(
            select(TradeCycle, Instrument)
            .join(Instrument, TradeCycle.conid == Instrument.conid)
            .where(
                TradeCycle.close_time.isnot(None),
                func.date(TradeCycle.close_time) >= date_from,
                func.date(TradeCycle.close_time) <= date_to,
            )
            .order_by(desc(TradeCycle.realized_pnl))
        )
    ).all()
    cycle_rows = [
        {
            "symbol": i.symbol,
            "direction": c.direction,
            "realized_pnl": float(c.realized_pnl or 0),
            "fees": float(c.fees_total or 0),
            "closed": c.close_time.isoformat()[:10],
        }
        for c, i in cycles
    ]

    return {
        "available": True,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "nav_start": float(points[0].nav),
        "nav_end": float(points[-1].nav),
        "twr": float(total_twr(returns)),
        "max_drawdown": float(dd.max_drawdown),
        "deposits": cash.get("DEPOSIT", 0.0),
        "withdrawals": cash.get("WITHDRAWAL", 0.0),
        "dividends": cash.get("DIVIDEND", 0.0) + cash.get("PAYMENT_IN_LIEU", 0.0),
        "fees_cash": cash.get("FEE", 0.0),
        "interest_net": cash.get("BROKER_INTEREST_RECEIVED", 0.0)
        + cash.get("BROKER_INTEREST_PAID", 0.0),
        "trades_count": trades_count,
        "best_cycles": cycle_rows[:5],
        "worst_cycles": sorted(cycle_rows, key=lambda r: r["realized_pnl"])[:5],
        "method_note": "תשואה: TWR יומי משורשר בנטרול הפקדות/משיכות; מקור הנתונים: Flex (daily_equity, cash_transactions)",
    }
