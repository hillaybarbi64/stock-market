"""Risk exposure math and insight rules on synthetic data."""

from datetime import UTC, datetime
from decimal import Decimal

from app.ibkr.types import AccountSummaryData, CashBalanceData, InstrumentData, PositionData
from app.services.insights import concentration_insights, fx_imbalance_insight
from app.services.risk import exposure_summary, stress_scenarios

NOW = datetime.now(UTC)
D = Decimal


def acct(nlv="10000", maint="1000", cash="2000") -> AccountSummaryData:
    return AccountSummaryData(
        ts=NOW, base_currency="USD", net_liquidation=D(nlv), maint_margin=D(maint), total_cash=D(cash)
    )


def pos(conid: int, symbol: str, mv: str, currency="USD") -> PositionData:
    return PositionData(
        ts=NOW,
        instrument=InstrumentData(conid=conid, symbol=symbol, sec_type="STK", currency=currency),
        quantity=D("10") if D(mv) >= 0 else D("-10"),
        market_value=D(mv),
    )


def test_exposure_long_short_and_concentration():
    exp = exposure_summary(
        acct(),
        [pos(1, "AAA", "5000"), pos(2, "BBB", "-2000"), pos(3, "CCC", "1000")],
        [],
        {1: "Tech", 2: None, 3: "Tech"},
    )
    assert exp is not None
    assert exp.long_exposure == 6000
    assert exp.short_exposure == 2000
    assert exp.gross_exposure == 8000
    assert exp.net_exposure == 4000
    assert abs(exp.top5_concentration - 0.8) < 1e-9  # (5000+2000+1000)/10000
    assert exp.sector_exposure["Tech"] == 6000
    assert exp.unclassified_value == 2000
    assert exp.margin_utilization == 0.1


def test_stress_scenarios_are_transparent():
    exp = exposure_summary(acct(), [pos(1, "AAA", "5000")], [], {})
    scenarios = stress_scenarios(exp)
    market10 = next(s for s in scenarios if "10%" in s["name"])
    assert market10["impact_base"] == -500  # net 5000 * 10%
    assert "Beta=1.0" in market10["assumptions"]
    biggest = next(s for s in scenarios if "AAA" in s["name"])
    assert biggest["impact_base"] == -1000


def test_fx_scenario_uses_non_base_exposure():
    exp = exposure_summary(
        acct(),
        [],
        [CashBalanceData(ts=NOW, currency="ILS", cash_balance=D("10000"), fx_rate_to_base=D("0.33"))],
        {},
    )
    fx = [s for s in stress_scenarios(exp) if "USD" in s["name"]]
    assert len(fx) == 2
    assert abs(fx[0]["impact_base"]) == round(3300 * 0.05, 2)


def test_concentration_insight_fires_at_threshold():
    exp = exposure_summary(acct(), [pos(1, "AAA", "2600"), pos(2, "BBB", "500")], [], {})
    drafts = concentration_insights(exp)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.kind == "position_concentration"
    assert d.severity == "WARN"
    assert d.evidence["symbol"] == "AAA"
    assert "26%" in d.title


def test_fx_imbalance_detects_negative_usd_with_idle_ils():
    """The real-world case: negative USD cash while ILS sits idle."""
    exp = exposure_summary(acct(), [pos(1, "AAA", "900")], [], {})
    drafts = fx_imbalance_insight(
        exp,
        [
            {"currency": "USD", "cash": -760.54, "cash_in_base": -760.54},
            {"currency": "ILS", "cash": 10000, "cash_in_base": 3305.05},
        ],
    )
    assert len(drafts) == 1
    assert drafts[0].kind == "fx_cash_imbalance"
    assert drafts[0].severity == "WARN"
    assert drafts[0].evidence["negative"]["currency"] == "USD"


def test_no_insights_without_data():
    exp = exposure_summary(acct(), [pos(1, "AAA", "500")], [], {})
    assert concentration_insights(exp) == []
    assert fx_imbalance_insight(exp, [{"currency": "USD", "cash": 100, "cash_in_base": 100}]) == []
