"""Flex parser: realistic Activity Flex fixture → normalized records."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.ibkr.flex_parser import MultipleFlexAccountsError, parse_flex_report

FIXTURE = (Path(__file__).parent / "fixtures" / "activity_flex_sample.xml").read_text()


def test_statement_metadata():
    report = parse_flex_report(FIXTURE)
    assert report.from_date == date(2026, 2, 17)
    assert report.to_date == date(2026, 7, 13)
    assert not report.skipped


def test_trades_parsed_with_costs():
    report = parse_flex_report(FIXTURE)
    assert len(report.trades) == 3
    sell = next(t for t in report.trades if t.side == "SELL")
    assert sell.exec_id == "00030f00.6a3949f9.01.01"
    assert sell.quantity == Decimal("10")  # stored positive; side carries direction
    assert sell.commission == Decimal("-1.5")
    assert sell.realized_pnl == Decimal("9.55")
    assert sell.instrument.symbol == "MXL"
    assert sell.trade_time.date() == date(2026, 6, 22)


def test_cash_transactions_typed():
    report = parse_flex_report(FIXTURE)
    by_type = {c.type: c for c in report.cash_transactions}
    assert by_type["DEPOSIT"].currency == "ILS"
    assert by_type["DEPOSIT"].amount == Decimal("10000")
    assert by_type["DEPOSIT"].fx_rate_to_base == Decimal("0.30078")
    assert by_type["DIVIDEND"].amount == Decimal("3.40")
    assert by_type["WITHHOLDING_TAX"].amount == Decimal("-0.85")
    assert by_type["BROKER_INTEREST_PAID"].amount == Decimal("-2.31")


def test_equity_summaries_and_positions():
    report = parse_flex_report(FIXTURE)
    assert len(report.equity_summaries) == 3
    first = report.equity_summaries[0]
    assert first.report_date == date(2026, 2, 17)
    assert first.total == Decimal("3008.30")
    assert len(report.open_positions) == 1
    assert report.open_positions[0].quantity == Decimal("8")


def test_corporate_actions_and_fx():
    report = parse_flex_report(FIXTURE)
    assert len(report.corporate_actions) == 1
    assert report.corporate_actions[0].type == "FS"
    assert len(report.fx_rates) == 2
    assert report.fx_rates[0].currency == "ILS"


def test_malformed_rows_are_skipped_not_fatal():
    broken = FIXTURE.replace('conid="431495220"', 'conid=""', 1)
    report = parse_flex_report(broken)
    # one Trade lost its conid → skipped and counted; everything else parses
    assert report.skipped.get("Trade") == 1
    assert len(report.trades) == 2


def test_multiple_accounts_are_rejected_before_any_ingestion():
    second_statement = (
        '<FlexStatement accountId="U9999999" fromDate="20260701" toDate="20260713" />'
    )
    multi_account = FIXTURE.replace(
        "</FlexStatements>",
        f"{second_statement}</FlexStatements>",
    )

    with pytest.raises(MultipleFlexAccountsError):
        parse_flex_report(multi_account)


def test_record_from_another_account_is_rejected():
    multi_account = FIXTURE.replace(
        '<Trade accountId="U7654321"',
        '<Trade accountId="U9999999"',
        1,
    )

    with pytest.raises(MultipleFlexAccountsError):
        parse_flex_report(multi_account)


def test_statement_without_account_is_rejected():
    missing_account = FIXTURE.replace(' accountId="U7654321"', "", 1)

    with pytest.raises(MultipleFlexAccountsError):
        parse_flex_report(missing_account)
