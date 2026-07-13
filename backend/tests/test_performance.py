"""Performance engine edge cases (see PERFORMANCE_CALCULATIONS.md §8)."""

from datetime import date, timedelta
from decimal import Decimal

from app.services.performance import (
    DayPoint,
    annualized_return,
    chain_returns,
    daily_returns,
    drawdown,
    monthly_returns,
    period_return,
    sharpe_ratio,
    total_twr,
    xirr,
)

D = Decimal


def dp(day: str, nav: str, flow: str = "0") -> DayPoint:
    return DayPoint(date.fromisoformat(day), D(nav), D(flow))


# ── TWR ──────────────────────────────────────────────────


def test_simple_gain_no_flows():
    rs = daily_returns([dp("2026-01-01", "1000"), dp("2026-01-02", "1100")])
    assert rs == [(date(2026, 1, 2), D("0.1"))]


def test_deposit_is_not_performance():
    """NAV 1000 → 2010 solely because of a 1000 deposit + 10 gain: the daily
    return must be ~0.5%, not 101%."""
    rs = daily_returns([dp("2026-01-01", "1000"), dp("2026-01-02", "2010", flow="1000")])
    assert rs[0][1] == D("10") / D("2000")


def test_withdrawal_mid_period():
    """1000 → withdraw 500 at start of day, ends at 510: gain of 10 on 500."""
    rs = daily_returns([dp("2026-01-01", "1000"), dp("2026-01-02", "510", flow="-500")])
    assert rs[0][1] == D("10") / D("500")


def test_twr_chains_across_flows():
    points = [
        dp("2026-01-01", "1000"),
        dp("2026-01-02", "1100"),            # +10%
        dp("2026-01-03", "2090", "1000"),    # deposit, then −0.476%
    ]
    rs = daily_returns(points)
    cum = total_twr(rs)
    expected = (1 + D("0.1")) * (D("2090") / D("2100")) - 1
    assert abs(cum - expected) < D("1e-12")


def test_empty_account_days_do_not_poison():
    rs = daily_returns([dp("2026-01-01", "0"), dp("2026-01-02", "0")])
    assert rs[0][1] == 0


def test_portfolio_without_trades_flat():
    rs = daily_returns([dp("2026-01-01", "1000"), dp("2026-01-02", "1000")])
    assert total_twr(rs) == 0


# ── Drawdown ─────────────────────────────────────────────


def test_drawdown_on_twr_not_nav():
    """A deposit that doubles NAV must not look like recovery: returns are
    flat→−10%→flat, so drawdown stays −10% regardless of NAV jumps."""
    returns = [
        (date(2026, 1, 2), D("0")),
        (date(2026, 1, 3), D("-0.10")),
        (date(2026, 1, 4), D("0")),
    ]
    dd = drawdown(chain_returns(returns))
    assert abs(dd.max_drawdown - D("-0.10")) < D("1e-12")
    assert dd.recovery_days is None  # never back to peak


def test_drawdown_recovery_counted():
    returns = [
        (date(2026, 1, 2), D("-0.10")),
        (date(2026, 1, 3), D("0.111111111111")),
    ]
    dd = drawdown(chain_returns(returns))
    assert dd.recovery_days == 1 or abs(dd.series[-1][1]) < D("1e-9")


# ── XIRR ─────────────────────────────────────────────────


def test_xirr_simple_year():
    """-1000 → +1100 after exactly one year ⇒ 10%."""
    flows = [(date(2025, 1, 1), D("-1000")), (date(2026, 1, 1), D("1100"))]
    assert abs(xirr(flows) - 0.10) < 1e-6


def test_xirr_mid_period_deposit():
    flows = [
        (date(2026, 1, 1), D("-1000")),
        (date(2026, 7, 1), D("-1000")),
        (date(2026, 12, 31), D("2200")),
    ]
    r = xirr(flows)
    assert r is not None and 0.10 < r < 0.20


def test_xirr_no_sign_change_is_none():
    assert xirr([(date(2026, 1, 1), D("-100")), (date(2026, 2, 1), D("-100"))]) is None


def test_xirr_single_flow_is_none():
    assert xirr([(date(2026, 1, 1), D("-100"))]) is None


# ── Gates ────────────────────────────────────────────────


def test_sharpe_insufficient_data_is_gated():
    rs = [(date(2026, 1, 1) + timedelta(days=i), D("0.001")) for i in range(10)]
    g = sharpe_ratio(rs)
    assert g.sufficient is False
    assert g.value is None
    assert g.available == 10
    assert g.required == 60


def test_sharpe_with_enough_data():
    rs = [
        (date(2026, 1, 1) + timedelta(days=i), D("0.001") * (1 if i % 2 else -1))
        for i in range(80)
    ]
    g = sharpe_ratio(rs)
    assert g.sufficient is True
    assert g.value is not None


def test_annualize_short_period_refused():
    g = annualized_return(D("0.05"), days_elapsed=30)
    assert g.sufficient is False and g.value is None


# ── Aggregations ─────────────────────────────────────────


def test_monthly_returns_compound():
    rs = [
        (date(2026, 1, 10), D("0.10")),
        (date(2026, 1, 20), D("0.10")),
        (date(2026, 2, 5), D("-0.05")),
    ]
    m = monthly_returns(rs)
    assert abs(m["2026-01"] - D("0.21")) < D("1e-12")
    assert m["2026-02"] == D("-0.05")


def test_period_return_window():
    rs = [
        (date(2026, 1, 10), D("0.10")),
        (date(2026, 2, 10), D("0.10")),
    ]
    assert period_return(rs, date(2026, 2, 1)) == D("0.10")
    assert period_return(rs, date(2026, 3, 1)) is None
