"""Performance endpoints: computed from locally-synced daily equity + cash
transactions. Method notes are returned alongside values (see
PERFORMANCE_CALCULATIONS.md); insufficient-data metrics say so explicitly."""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import CashTransaction, DailyEquity
from app.services.performance import (
    DayPoint,
    annualized_return,
    chain_returns,
    daily_returns,
    drawdown,
    monthly_returns,
    period_return,
    sharpe_ratio,
    sortino_ratio,
    total_twr,
    volatility_annualized,
    xirr,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_points(db: AsyncSession) -> list[DayPoint]:
    rows = (
        (await db.execute(select(DailyEquity).order_by(DailyEquity.equity_date))).scalars().all()
    )
    return [
        DayPoint(day=r.equity_date, nav=r.nav, flow=(r.deposits or 0) - (r.withdrawals or 0))
        for r in rows
    ]


@router.get("/summary")
async def performance_summary(db: DbSession) -> dict:
    points = await _load_points(db)
    if len(points) < 2:
        return {
            "available": False,
            "days_available": len(points),
            "detail": "נדרשים לפחות 2 ימי NAV מסונכרנים. הרץ סנכרון Flex (מסך סנכרון).",
        }

    returns = daily_returns(points)
    cum = chain_returns(returns)
    dd = drawdown(cum)
    last_day = points[-1].day
    first_day = points[0].day
    days_elapsed = (last_day - first_day).days

    def pr(start: date) -> float | None:
        r = period_return(returns, start)
        return float(r) if r is not None else None

    # Money-weighted: opening NAV as initial investment, then external flows,
    # then closing NAV back — investor perspective.
    flows: list[tuple[date, Decimal]] = [(first_day, -points[0].nav)]
    flows += [(p.day, -p.flow) for p in points[1:] if p.flow != 0]
    flows.append((last_day, points[-1].nav))
    mwr = xirr(flows)

    cash_totals = dict(
        (
            await db.execute(
                select(
                    CashTransaction.type,
                    func.sum(
                        CashTransaction.amount * func.coalesce(CashTransaction.fx_rate_to_base, 1)
                    ),
                ).group_by(CashTransaction.type)
            )
        ).all()
    )

    def total(*types: str) -> float:
        return float(sum(cash_totals.get(t, 0) for t in types))

    ann = annualized_return(total_twr(returns), days_elapsed)
    vol = volatility_annualized(returns)
    shp = sharpe_ratio(returns)
    srt = sortino_ratio(returns)

    return {
        "available": True,
        "as_of": last_day.isoformat(),
        "since": first_day.isoformat(),
        "days_available": len(points),
        "method": {
            "twr": "Time-Weighted Return, תזרימים בתחילת יום (תואם IBKR)",
            "mwr": "XIRR על הפקדות/משיכות + שווי פתיחה/סגירה",
            "source": "daily_equity (Flex) + cash_transactions (Flex)",
        },
        "returns": {
            "total_twr": float(total_twr(returns)),
            "day": pr(last_day),
            "wtd": pr(last_day - timedelta(days=last_day.weekday())),
            "mtd": pr(last_day.replace(day=1)),
            "ytd": pr(last_day.replace(month=1, day=1)),
            "one_year": pr(last_day - timedelta(days=365)),
            "annualized": asdict(ann),
            "xirr": mwr,
        },
        "risk": {
            "max_drawdown": float(dd.max_drawdown),
            "max_drawdown_date": dd.max_drawdown_date.isoformat() if dd.max_drawdown_date else None,
            "current_drawdown": float(dd.current_drawdown),
            "recovery_days": dd.recovery_days,
            "volatility": asdict(vol),
            "sharpe": asdict(shp),
            "sortino": asdict(srt),
        },
        "cash": {
            "deposits": total("DEPOSIT"),
            "withdrawals": total("WITHDRAWAL"),
            "dividends": total("DIVIDEND", "PAYMENT_IN_LIEU"),
            "withholding_tax": total("WITHHOLDING_TAX"),
            "fees": total("FEE", "COMMISSION_ADJ"),
            "interest_net": total("BROKER_INTEREST_RECEIVED") + total("BROKER_INTEREST_PAID"),
        },
    }


@router.get("/equity-curve")
async def equity_curve(db: DbSession) -> dict:
    points = await _load_points(db)
    if len(points) < 2:
        return {"available": False, "points": []}
    returns = daily_returns(points)
    cum = chain_returns(returns)
    dd = drawdown(cum)
    cum_by_day = dict(cum)
    dd_by_day = dict(dd.series)
    return {
        "available": True,
        "points": [
            {
                "date": p.day.isoformat(),
                "nav": float(p.nav),
                "cum_return": float(cum_by_day.get(p.day, 0)),
                "drawdown": float(dd_by_day.get(p.day, 0)),
                "flow": float(p.flow),
            }
            for p in points
        ],
    }


@router.get("/monthly")
async def monthly(db: DbSession) -> dict:
    points = await _load_points(db)
    if len(points) < 2:
        return {"available": False, "months": {}}
    returns = daily_returns(points)
    return {
        "available": True,
        "months": {k: float(v) for k, v in sorted(monthly_returns(returns).items())},
    }


@router.get("/daily")
async def daily(db: DbSession) -> dict:
    """Per-day P&L and return — feeds the calendar heatmap."""
    points = await _load_points(db)
    if len(points) < 2:
        return {"available": False, "days": []}
    returns = dict(daily_returns(points))
    out = []
    for prev, cur in zip(points, points[1:], strict=False):
        pnl = cur.nav - prev.nav - cur.flow
        out.append(
            {
                "date": cur.day.isoformat(),
                "pnl": float(pnl),
                "return": float(returns.get(cur.day, 0)),
            }
        )
    return {"available": True, "days": out}
