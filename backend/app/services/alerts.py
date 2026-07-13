"""Alert rules evaluation.

Rules are user-defined thresholds over live metrics. Evaluation runs on
account snapshots (and can be triggered manually). Events are stored and
pushed over the WebSocket; delivery channels beyond in-app (email/telegram)
are a documented future extension.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import AlertEvent, AlertRule, DailyEquity
from app.services.risk import ExposureSummary
from app.ws.hub import WsHub

log = get_logger(__name__)

SUPPORTED_METRICS = {
    "daily_loss_pct": "הפסד יומי (% מה-NLV, חיובי=הפסד)",
    "position_weight_pct": "משקל הפוזיציה הגדולה (%)",
    "margin_utilization_pct": "ניצול מרג'ין (%)",
    "excess_liquidity": "Excess Liquidity (במטבע הבסיס)",
    "drawdown_pct": "Drawdown נוכחי (%, חיובי=עומק)",
}

_OPS = {
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}

# one event per rule per cooldown window — no alert storms
COOLDOWN = timedelta(hours=6)


async def evaluate_rules(
    exposure: ExposureSummary | None,
    daily_pnl: float | None,
    excess_liquidity: float | None,
    current_drawdown_pct: float | None,
    hub: WsHub | None = None,
) -> int:
    values: dict[str, float | None] = {
        "daily_loss_pct": (
            (-daily_pnl / exposure.nlv * 100) if daily_pnl is not None and exposure and exposure.nlv else None
        ),
        "position_weight_pct": (
            exposure.positions[0]["weight"] * 100 if exposure and exposure.positions else None
        ),
        "margin_utilization_pct": (
            exposure.margin_utilization * 100
            if exposure and exposure.margin_utilization is not None
            else None
        ),
        "excess_liquidity": excess_liquidity,
        "drawdown_pct": (-current_drawdown_pct * 100) if current_drawdown_pct is not None else None,
    }

    fired = 0
    async with db_session() as session:
        rules = (
            (await session.execute(select(AlertRule).where(AlertRule.enabled.is_(True))))
            .scalars()
            .all()
        )
        for rule in rules:
            value = values.get(rule.metric)
            if value is None or rule.operator not in _OPS:
                continue
            if not _OPS[rule.operator](value, float(rule.threshold)):
                continue
            recent = (
                await session.execute(
                    select(AlertEvent.fired_at)
                    .where(AlertEvent.rule_id == rule.id)
                    .order_by(desc(AlertEvent.fired_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if recent and datetime.now(UTC) - recent < COOLDOWN:
                continue
            message = f"{rule.name}: {rule.metric} = {value:,.2f} (סף: {rule.operator} {rule.threshold})"
            event = AlertEvent(
                rule_id=rule.id, fired_at=datetime.now(UTC), value=value, message=message
            )
            session.add(event)
            fired += 1
            log.info("alert_fired", rule=rule.name, value=value)
            if hub is not None:
                await hub.publish("alert", {"rule": rule.name, "message": message, "value": value})
        await session.commit()
    return fired


async def latest_drawdown_pct() -> float | None:
    """Current drawdown from stored daily equity (TWR-based, simplified to
    NAV-peak when flows are absent in window)."""
    async with db_session() as session:
        rows = (
            (await session.execute(select(DailyEquity).order_by(DailyEquity.equity_date)))
            .scalars()
            .all()
        )
    if len(rows) < 2:
        return None
    from app.services.performance import DayPoint, chain_returns, daily_returns, drawdown

    points = [
        DayPoint(day=r.equity_date, nav=r.nav, flow=(r.deposits or 0) - (r.withdrawals or 0))
        for r in rows
    ]
    return float(drawdown(chain_returns(daily_returns(points))).current_drawdown)
