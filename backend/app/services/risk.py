"""Risk analytics: exposure, concentration, stress scenarios.

Stress tests are parametric what-ifs, not forecasts. Every scenario returns
its assumptions verbatim so the user can judge them. Metrics that need data
we don't have yet (per-position price history → correlations, betas) are
reported as unavailable instead of being approximated silently.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.ibkr.types import AccountSummaryData, CashBalanceData, PositionData


@dataclass(frozen=True)
class ExposureSummary:
    base_currency: str
    nlv: float
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    gross_leverage: float | None  # gross / nlv
    cash_pct: float | None
    margin_utilization: float | None  # maint margin / nlv
    positions: list[dict]
    top5_concentration: float | None
    top10_concentration: float | None
    currency_exposure: dict[str, float]
    sector_exposure: dict[str, float]
    unclassified_value: float


def exposure_summary(
    account: AccountSummaryData,
    positions: list[PositionData],
    balances: list[CashBalanceData],
    sectors: dict[int, str | None],
) -> ExposureSummary | None:
    if account.net_liquidation in (None, 0):
        return None
    nlv = float(account.net_liquidation)

    rows = []
    long_exp = short_exp = Decimal(0)
    ccy_exp: dict[str, Decimal] = {}
    sector_exp: dict[str, Decimal] = {}
    unclassified = Decimal(0)

    for p in positions:
        if p.quantity == 0 or p.market_value is None:
            continue
        mv = p.market_value
        if mv >= 0:
            long_exp += mv
        else:
            short_exp += -mv
        ccy_exp[p.instrument.currency] = ccy_exp.get(p.instrument.currency, Decimal(0)) + abs(mv)
        sector = sectors.get(p.instrument.conid)
        if sector:
            sector_exp[sector] = sector_exp.get(sector, Decimal(0)) + abs(mv)
        else:
            unclassified += abs(mv)
        rows.append(
            {
                "conid": p.instrument.conid,
                "symbol": p.instrument.symbol,
                "market_value": float(mv),
                "weight": float(abs(mv)) / nlv,
                "direction": "LONG" if mv >= 0 else "SHORT",
                "currency": p.instrument.currency,
                "sector": sector,
            }
        )

    # cash in non-base currencies is currency exposure too
    for b in balances:
        if b.currency == account.base_currency or b.cash_balance == 0:
            continue
        in_base = b.cash_balance * (b.fx_rate_to_base or 1)
        ccy_exp[b.currency] = ccy_exp.get(b.currency, Decimal(0)) + abs(in_base)

    rows.sort(key=lambda r: -abs(r["market_value"]))
    weights = [r["weight"] for r in rows]
    gross = float(long_exp + short_exp)
    total_cash = float(account.total_cash) if account.total_cash is not None else None

    return ExposureSummary(
        base_currency=account.base_currency,
        nlv=nlv,
        gross_exposure=gross,
        net_exposure=float(long_exp - short_exp),
        long_exposure=float(long_exp),
        short_exposure=float(short_exp),
        gross_leverage=gross / nlv if nlv else None,
        cash_pct=(total_cash / nlv) if total_cash is not None and nlv else None,
        margin_utilization=(
            float(account.maint_margin) / nlv if account.maint_margin is not None and nlv else None
        ),
        positions=rows,
        top5_concentration=sum(weights[:5]) if weights else None,
        top10_concentration=sum(weights[:10]) if weights else None,
        currency_exposure={k: float(v) for k, v in sorted(ccy_exp.items())},
        sector_exposure={k: float(v) for k, v in sorted(sector_exp.items())},
        unclassified_value=float(unclassified),
    )


def stress_scenarios(summary: ExposureSummary) -> list[dict]:
    """Parametric scenarios. Beta is assumed 1.0 per equity position unless a
    measured beta exists (it doesn't yet) — stated in the assumptions."""
    nlv = summary.nlv
    scenarios: list[dict] = []

    for pct in (5, 10, 20):
        impact = -summary.net_exposure * pct / 100
        scenarios.append(
            {
                "name": f"ירידה של {pct}% בשוק",
                "assumptions": "כל פוזיציה זזה עם השוק (Beta=1.0 מונח, לא נמדד); מזומן ללא שינוי; ללא מתאם בין-נכסי מעבר לכך",
                "impact_base": round(impact, 2),
                "impact_pct_nlv": round(impact / nlv, 4) if nlv else None,
                "nlv_after": round(nlv + impact, 2),
            }
        )

    if summary.positions:
        biggest = summary.positions[0]
        impact = -abs(biggest["market_value"]) * Decimal("0.2").__float__()
        scenarios.append(
            {
                "name": f"ירידה של 20% בפוזיציה הגדולה ({biggest['symbol']})",
                "assumptions": "רק הפוזיציה הגדולה יורדת; שאר התיק ללא שינוי",
                "impact_base": round(impact, 2),
                "impact_pct_nlv": round(impact / nlv, 4) if nlv else None,
                "nlv_after": round(nlv + impact, 2),
            }
        )

    non_base = {k: v for k, v in summary.currency_exposure.items() if k != summary.base_currency}
    if non_base:
        total_fx = sum(non_base.values())
        for direction, sign in (("התחזקות", -1), ("היחלשות", 1)):
            impact = sign * total_fx * 0.05
            scenarios.append(
                {
                    "name": f"{direction} {summary.base_currency} ב-5% מול שאר המטבעות",
                    "assumptions": f"חשיפת מט\"ח שאינה {summary.base_currency}: "
                    f"{round(total_fx, 2)} (פוזיציות + מזומן); תזוזה אחידה של 5%",
                    "impact_base": round(impact, 2),
                    "impact_pct_nlv": round(impact / nlv, 4) if nlv else None,
                    "nlv_after": round(nlv + impact, 2),
                }
            )

    return scenarios
