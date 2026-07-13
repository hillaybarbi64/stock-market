"""Rule-based insights engine.

Every insight is grounded in concrete data (returned as `evidence`), carries
severity + confidence, and states its assumptions. No generic advice, no
fabrication when data is missing — a rule that lacks data emits nothing.
Insights are recommendations to CHECK something, never automatic actions.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CashTransaction, TradeCycle
from app.services.risk import ExposureSummary

DEFAULT_THRESHOLDS = {
    "position_weight_warn": 0.20,
    "position_weight_alert": 0.35,
    "sector_weight_warn": 0.40,
    "fees_vs_profit_warn": 0.25,
    "margin_utilization_warn": 0.30,
}


@dataclass(frozen=True)
class InsightDraft:
    kind: str
    severity: str  # INFO | WARN | ALERT
    confidence: str  # LOW | MED | HIGH
    title: str
    body: str
    evidence: dict
    assumptions: str | None = None
    link: str | None = None


def concentration_insights(exp: ExposureSummary, thresholds=DEFAULT_THRESHOLDS) -> list[InsightDraft]:
    out: list[InsightDraft] = []
    for pos in exp.positions:
        w = pos["weight"]
        if w >= thresholds["position_weight_alert"]:
            severity = "ALERT"
        elif w >= thresholds["position_weight_warn"]:
            severity = "WARN"
        else:
            continue
        out.append(
            InsightDraft(
                kind="position_concentration",
                severity=severity,
                confidence="HIGH",
                title=f"ריכוזיות גבוהה: {pos['symbol']} מהווה {w:.0%} מהתיק",
                body=(
                    f"הפוזיציה ב-{pos['symbol']} שווה {pos['market_value']:,.0f} "
                    f"{exp.base_currency} מתוך NLV של {exp.nlv:,.0f}. "
                    f"ירידה של 20% בפוזיציה לבדה תשפיע על התיק בכ-{w * 0.2:.1%}. "
                    "כדאי לבדוק אם הריכוזיות תואמת את התוכנית שלך."
                ),
                evidence={"symbol": pos["symbol"], "weight": w, "market_value": pos["market_value"], "nlv": exp.nlv},
                assumptions=f"סף אזהרה: {thresholds['position_weight_warn']:.0%}; סף התראה: {thresholds['position_weight_alert']:.0%} (ניתן לשינוי בהגדרות)",
                link="/positions",
            )
        )
    return out


def fx_imbalance_insight(exp: ExposureSummary, balances_summary: list[dict]) -> list[InsightDraft]:
    """Negative cash in one currency alongside idle cash in another —
    paying margin interest while cash sits unconverted."""
    negative = [b for b in balances_summary if b["cash"] < 0]
    positive_other = [b for b in balances_summary if b["cash"] > 0 and b["currency"] != exp.base_currency]
    out = []
    for neg in negative:
        covering = [p for p in positive_other if p["currency"] != neg["currency"]]
        if not covering:
            continue
        cover_total = sum(p["cash_in_base"] for p in covering)
        if cover_total <= 0:
            continue
        out.append(
            InsightDraft(
                kind="fx_cash_imbalance",
                severity="WARN",
                confidence="HIGH",
                title=f"יתרה שלילית ב-{neg['currency']} לצד מזומן פנוי במטבע אחר",
                body=(
                    f"יתרת המזומן ב-{neg['currency']} שלילית ({neg['cash']:,.0f}) — על יתרה שלילית "
                    f"IBKR גובה ריבית — בעוד שקיים מזומן פנוי בשווי {cover_total:,.0f} "
                    f"{exp.base_currency} במטבעות אחרים "
                    f"({', '.join(p['currency'] for p in covering)}). "
                    "שווה לבדוק האם המרת מטבע תחסוך את עלות הריבית."
                ),
                evidence={"negative": neg, "available_other": covering},
                assumptions="ריבית חובה נגבית על יתרות שליליות לפי תעריפי IBKR; ההמלצה היא לבדוק, לא הוראה לפעולה",
                link="/",
            )
        )
    return out


def margin_insight(exp: ExposureSummary, thresholds=DEFAULT_THRESHOLDS) -> list[InsightDraft]:
    if exp.margin_utilization is None or exp.margin_utilization < thresholds["margin_utilization_warn"]:
        return []
    return [
        InsightDraft(
            kind="margin_utilization",
            severity="WARN",
            confidence="HIGH",
            title=f"ניצול מרג'ין {exp.margin_utilization:.0%} מה-NLV",
            body=(
                f"דרישת ה-Maintenance Margin היא {exp.margin_utilization:.0%} משווי החשבון. "
                "ירידה חדה בשוק תקטין את ה-Excess Liquidity ועלולה להתקרב לרמת חיסול כפוי."
            ),
            evidence={"margin_utilization": exp.margin_utilization, "nlv": exp.nlv},
            assumptions=f"סף: {thresholds['margin_utilization_warn']:.0%}",
            link="/risk",
        )
    ]


async def behavior_insights(db: AsyncSession) -> list[InsightDraft]:
    """Patterns from closed cycles. Only emitted with a minimal sample."""
    cycles = (
        (await db.execute(select(TradeCycle).where(TradeCycle.close_time.isnot(None))))
        .scalars()
        .all()
    )
    out: list[InsightDraft] = []
    closed = [c for c in cycles if c.realized_pnl is not None]
    if len(closed) >= 6:
        winners = [c for c in closed if c.realized_pnl > 0]
        losers = [c for c in closed if c.realized_pnl <= 0]
        if len(winners) >= 3 and len(losers) >= 3:
            avg_w = sum((c.close_time - c.open_time).days for c in winners) / len(winners)
            avg_l = sum((c.close_time - c.open_time).days for c in losers) / len(losers)
            if avg_l > avg_w * 1.5:
                out.append(
                    InsightDraft(
                        kind="holding_losers_longer",
                        severity="INFO",
                        confidence="MED",
                        title="עסקאות מפסידות מוחזקות זמן רב יותר ממנצחות",
                        body=(
                            f"משך החזקה ממוצע: מפסידות {avg_l:.0f} ימים לעומת {avg_w:.0f} "
                            f"במנצחות ({len(losers)} מול {len(winners)} עסקאות). "
                            "דפוס כזה מקושר לעיתים להימנעות ממימוש הפסד. מתאם — לא הוכחת סיבתיות."
                        ),
                        evidence={"avg_days_losers": avg_l, "avg_days_winners": avg_w,
                                  "losers": len(losers), "winners": len(winners)},
                        assumptions="מדגם קטן; נדרשות לפחות 3 עסקאות בכל קבוצה",
                        link="/journal",
                    )
                )

    fees_rows = (
        await db.execute(
            select(CashTransaction.amount, CashTransaction.fx_rate_to_base).where(
                CashTransaction.type.in_(("FEE", "COMMISSION_ADJ"))
            )
        )
    ).all()
    commissions = sum((abs(c.fees_total or 0) for c in closed), Decimal(0))
    other_fees = sum((abs(a) * (fx or 1) for a, fx in fees_rows), Decimal(0))
    gross_profit = sum((c.realized_pnl for c in closed if c.realized_pnl > 0), Decimal(0))
    total_fees = commissions + other_fees
    if gross_profit > 0 and total_fees / gross_profit >= Decimal(str(DEFAULT_THRESHOLDS["fees_vs_profit_warn"])):
        out.append(
            InsightDraft(
                kind="fees_erode_profit",
                severity="WARN",
                confidence="HIGH",
                title=f"עלויות מסחר שוות {float(total_fees / gross_profit):.0%} מהרווח הגולמי",
                body=(
                    f"עמלות ({float(commissions):,.2f}) ועלויות אחרות ({float(other_fees):,.2f}) "
                    f"מול רווח גולמי של {float(gross_profit):,.2f}. "
                    "בחשבון קטן, עסקאות קטנות ותכופות מגדילות את משקל העמלה."
                ),
                evidence={"commissions": float(commissions), "other_fees": float(other_fees),
                          "gross_profit": float(gross_profit)},
                assumptions=f"סף: {DEFAULT_THRESHOLDS['fees_vs_profit_warn']:.0%} מהרווח הגולמי",
                link="/trades",
            )
        )
    return out
