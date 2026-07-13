"""Alert evaluation (thresholds, cooldown) and CSV export sanity."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select

from app.db.base import db_session, dispose_engine
from app.db.models import AlertEvent, AlertRule
from app.ibkr.types import AccountSummaryData, InstrumentData, PositionData
from app.services.alerts import evaluate_rules
from app.services.risk import exposure_summary

NOW = datetime.now(UTC)


def make_exposure(nlv="10000", pos_mv="3000"):
    return exposure_summary(
        AccountSummaryData(ts=NOW, base_currency="USD", net_liquidation=Decimal(nlv)),
        [
            PositionData(
                ts=NOW,
                instrument=InstrumentData(9901, "TST", "STK", "USD"),
                quantity=Decimal("10"),
                market_value=Decimal(pos_mv),
            )
        ],
        [],
        {},
    )


async def _cleanup():
    async with db_session() as s:
        await s.execute(delete(AlertEvent))
        await s.execute(delete(AlertRule))
        await s.commit()


async def test_rule_fires_once_within_cooldown():
    await _cleanup()
    try:
        async with db_session() as s:
            s.add(AlertRule(name="הפסד יומי", metric="daily_loss_pct", operator="gt",
                            threshold=2, enabled=True, created_at=NOW))
            await s.commit()

        exp = make_exposure()
        fired1 = await evaluate_rules(exp, daily_pnl=-300, excess_liquidity=None,
                                      current_drawdown_pct=None)  # loss 3% > 2%
        fired2 = await evaluate_rules(exp, daily_pnl=-300, excess_liquidity=None,
                                      current_drawdown_pct=None)  # cooldown → silent
        assert fired1 == 1
        assert fired2 == 0
        async with db_session() as s:
            events = (await s.execute(select(AlertEvent))).scalars().all()
        assert len(events) == 1
        assert "daily_loss_pct" in events[0].message
    finally:
        await _cleanup()
        await dispose_engine()


async def test_rule_does_not_fire_below_threshold():
    await _cleanup()
    try:
        async with db_session() as s:
            s.add(AlertRule(name="משקל פוזיציה", metric="position_weight_pct", operator="gt",
                            threshold=50, enabled=True, created_at=NOW))
            await s.commit()
        fired = await evaluate_rules(make_exposure(pos_mv="3000"), None, None, None)  # 30% < 50%
        assert fired == 0
    finally:
        await _cleanup()
        await dispose_engine()


async def test_missing_metric_value_is_skipped():
    await _cleanup()
    try:
        async with db_session() as s:
            s.add(AlertRule(name="DD", metric="drawdown_pct", operator="gt",
                            threshold=10, enabled=True, created_at=NOW))
            await s.commit()
        fired = await evaluate_rules(None, None, None, None)  # no data at all
        assert fired == 0
    finally:
        await _cleanup()
        await dispose_engine()


async def test_csv_export_has_bom_and_header(client):
    resp = await client.get("/api/reports/export/daily_equity.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert body.startswith("﻿")  # UTF-8 BOM for Excel
    assert "date,nav" in body
