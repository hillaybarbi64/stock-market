"""Performance engine — pure calculation functions.

Definitions and assumptions are documented in PERFORMANCE_CALCULATIONS.md.
Key conventions:
- External flows (deposits +, withdrawals −) are assumed to occur at the
  START of the day (w=1), matching IBKR's own TWR convention.
- Returns are Decimals end-to-end until presentation.
- Every advanced metric enforces a minimum-data threshold and reports
  insufficiency instead of a falsely-precise number.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

TRADING_DAYS_PER_YEAR = 252
MIN_DAYS_RISK_METRICS = 60
MIN_DAYS_ANNUALIZE = 90


@dataclass(frozen=True)
class DayPoint:
    day: date
    nav: Decimal
    flow: Decimal  # deposits − withdrawals, in base currency


@dataclass(frozen=True)
class Gated:
    """A metric value with its data-sufficiency gate."""

    value: float | None
    sufficient: bool
    available: int
    required: int
    note: str | None = None


def daily_returns(points: list[DayPoint]) -> list[tuple[date, Decimal]]:
    """Time-weighted daily returns, flows at start of day:
    r_t = (NAV_t − NAV_{t−1} − F_t) / (NAV_{t−1} + F_t)
    Days with an undefined denominator (empty account) yield r=0 and are
    effectively skipped rather than poisoning the chain."""
    out: list[tuple[date, Decimal]] = []
    for prev, cur in zip(points, points[1:], strict=False):
        denom = prev.nav + cur.flow
        if denom == 0:
            out.append((cur.day, Decimal(0)))
            continue
        r = (cur.nav - prev.nav - cur.flow) / denom
        out.append((cur.day, r))
    return out


def chain_returns(returns: list[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    """Cumulative TWR series: ∏(1+r_t) − 1."""
    out: list[tuple[date, Decimal]] = []
    acc = Decimal(1)
    for day, r in returns:
        acc *= 1 + r
        out.append((day, acc - 1))
    return out


def total_twr(returns: list[tuple[date, Decimal]]) -> Decimal:
    acc = Decimal(1)
    for _, r in returns:
        acc *= 1 + r
    return acc - 1


@dataclass(frozen=True)
class DrawdownStats:
    series: list[tuple[date, Decimal]]  # drawdown (≤0) per day, off the TWR curve
    max_drawdown: Decimal
    max_drawdown_date: date | None
    current_drawdown: Decimal
    peak_date: date | None
    recovery_days: int | None  # trading days from trough back to peak; None if not recovered


def drawdown(cum_returns: list[tuple[date, Decimal]]) -> DrawdownStats:
    """Drawdown measured on the TWR curve (not raw NAV) so deposits never
    masquerade as recovery."""
    if not cum_returns:
        return DrawdownStats([], Decimal(0), None, Decimal(0), None, None)
    series: list[tuple[date, Decimal]] = []
    peak = Decimal(-1)
    peak_date: date | None = None
    max_dd = Decimal(0)
    max_dd_date: date | None = None
    trough_index: int | None = None
    for i, (day, cum) in enumerate(cum_returns):
        if cum > peak:
            peak = cum
            peak_date = day
        dd = (1 + cum) / (1 + peak) - 1
        series.append((day, dd))
        if dd < max_dd:
            max_dd = dd
            max_dd_date = day
            trough_index = i
    recovery_days: int | None = None
    if trough_index is not None:
        for j in range(trough_index + 1, len(series)):
            if series[j][1] == 0:
                recovery_days = j - trough_index
                break
    return DrawdownStats(
        series=series,
        max_drawdown=max_dd,
        max_drawdown_date=max_dd_date,
        current_drawdown=series[-1][1],
        peak_date=peak_date,
        recovery_days=recovery_days,
    )


def annualized_return(cum_return: Decimal, days_elapsed: int) -> Gated:
    if days_elapsed < MIN_DAYS_ANNUALIZE:
        return Gated(None, False, days_elapsed, MIN_DAYS_ANNUALIZE,
                     "תקופה קצרה מדי לאנואליזציה אמינה — מוצגת תשואה מצטברת בלבד")
    if cum_return <= Decimal(-1):
        return Gated(-1.0, True, days_elapsed, MIN_DAYS_ANNUALIZE)
    years = days_elapsed / 365.0
    # cum_return is a Decimal; the fractional power must be done in float
    # (Decimal ** float is unsupported).
    value = (1 + float(cum_return)) ** (1 / years) - 1
    return Gated(value, True, days_elapsed, MIN_DAYS_ANNUALIZE)


def _std(xs: list[float]) -> float:
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return var**0.5


def volatility_annualized(returns: list[tuple[date, Decimal]]) -> Gated:
    n = len(returns)
    if n < MIN_DAYS_RISK_METRICS:
        return Gated(None, False, n, MIN_DAYS_RISK_METRICS)
    daily = [float(r) for _, r in returns]
    return Gated(_std(daily) * TRADING_DAYS_PER_YEAR**0.5, True, n, MIN_DAYS_RISK_METRICS)


def sharpe_ratio(returns: list[tuple[date, Decimal]], risk_free_annual: float = 0.04) -> Gated:
    n = len(returns)
    if n < MIN_DAYS_RISK_METRICS:
        return Gated(None, False, n, MIN_DAYS_RISK_METRICS,
                     f"נדרשים {MIN_DAYS_RISK_METRICS} ימי מסחר, קיימים {n}")
    daily = [float(r) for _, r in returns]
    rf_daily = risk_free_annual / TRADING_DAYS_PER_YEAR
    excess = [r - rf_daily for r in daily]
    sd = _std(excess)
    if sd == 0:
        return Gated(None, False, n, MIN_DAYS_RISK_METRICS, "תנודתיות אפס — היחס אינו מוגדר")
    mean_annual = (sum(excess) / n) * TRADING_DAYS_PER_YEAR
    return Gated(mean_annual / (sd * TRADING_DAYS_PER_YEAR**0.5), True, n, MIN_DAYS_RISK_METRICS)


def sortino_ratio(returns: list[tuple[date, Decimal]], risk_free_annual: float = 0.04) -> Gated:
    n = len(returns)
    if n < MIN_DAYS_RISK_METRICS:
        return Gated(None, False, n, MIN_DAYS_RISK_METRICS)
    rf_daily = risk_free_annual / TRADING_DAYS_PER_YEAR
    excess = [float(r) - rf_daily for _, r in returns]
    downside = [min(0.0, x) for x in excess]
    dd_var = sum(x**2 for x in downside) / len(excess)
    if dd_var == 0:
        return Gated(None, False, n, MIN_DAYS_RISK_METRICS, "אין ימי ירידה בתקופה — היחס אינו מוגדר")
    mean_annual = (sum(excess) / n) * TRADING_DAYS_PER_YEAR
    return Gated(mean_annual / ((dd_var**0.5) * TRADING_DAYS_PER_YEAR**0.5), True, n, MIN_DAYS_RISK_METRICS)


def xirr(flows: list[tuple[date, Decimal]]) -> float | None:
    """Money-weighted annual return. flows: investor perspective —
    deposits negative, withdrawals positive, final NAV positive at end date.
    Returns None when undefined (no sign change, no convergence, <2 flows)."""
    if len(flows) < 2:
        return None
    flows = sorted(flows, key=lambda f: f[0])
    amounts = [float(a) for _, a in flows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None
    t0 = flows[0][0]
    times = [(d - t0).days / 365.0 for d, _ in flows]

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** t for a, t in zip(amounts, times, strict=True))

    lo, hi = -0.9999, 100.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def monthly_returns(returns: list[tuple[date, Decimal]]) -> dict[str, Decimal]:
    """'YYYY-MM' → compounded return of that month's daily returns."""
    out: dict[str, Decimal] = {}
    acc: dict[str, Decimal] = {}
    for day, r in returns:
        key = f"{day.year:04d}-{day.month:02d}"
        acc[key] = acc.get(key, Decimal(1)) * (1 + r)
    for key, product in acc.items():
        out[key] = product - 1
    return out


def period_return(returns: list[tuple[date, Decimal]], start: date) -> Decimal | None:
    """Compounded return from `start` (inclusive) to the end of the series."""
    window = [(d, r) for d, r in returns if d >= start]
    if not window:
        return None
    return total_twr(window)
