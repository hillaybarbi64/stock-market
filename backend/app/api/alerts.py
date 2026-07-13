"""Alert rules CRUD + events + manual evaluation."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import AlertEvent, AlertRule
from app.ibkr.types import GatewayState
from app.services import registry
from app.services.alerts import SUPPORTED_METRICS, evaluate_rules, latest_drawdown_pct
from app.ws.hub import hub

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


class RuleIn(BaseModel):
    name: str = Field(max_length=128)
    metric: Literal[
        "daily_loss_pct", "position_weight_pct", "margin_utilization_pct",
        "excess_liquidity", "drawdown_pct",
    ]
    operator: Literal["gt", "gte", "lt", "lte"]
    threshold: float
    enabled: bool = True


@router.get("/metrics")
async def metrics() -> dict:
    return {"metrics": SUPPORTED_METRICS}


@router.get("/rules")
async def list_rules(db: DbSession) -> dict:
    rows = (await db.execute(select(AlertRule).order_by(AlertRule.id))).scalars().all()
    return {
        "rules": [
            {
                "id": r.id, "name": r.name, "metric": r.metric, "operator": r.operator,
                "threshold": float(r.threshold), "enabled": r.enabled,
            }
            for r in rows
        ]
    }


@router.post("/rules")
async def create_rule(payload: RuleIn, db: DbSession) -> dict:
    rule = AlertRule(created_at=datetime.now(UTC), **payload.model_dump())
    db.add(rule)
    await db.commit()
    return {"id": rule.id}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, db: DbSession) -> dict:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(404, "rule not found")
    await db.delete(rule)
    await db.commit()
    return {"ok": True}


@router.get("/events")
async def list_events(db: DbSession) -> dict:
    rows = (
        await db.execute(
            select(AlertEvent, AlertRule)
            .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
            .order_by(desc(AlertEvent.fired_at))
            .limit(50)
        )
    ).all()
    return {
        "events": [
            {
                "id": e.id, "rule": r.name, "fired_at": e.fired_at.isoformat(),
                "value": float(e.value), "message": e.message,
                "acknowledged": e.acknowledged_at is not None,
            }
            for e, r in rows
        ]
    }


@router.post("/evaluate")
async def evaluate_now(db: DbSession) -> dict:
    live = registry.live_state
    exposure = None
    daily_pnl = None
    excess = None
    if live and live.account and live.connection.state == GatewayState.CONNECTED:
        from app.db.models import Instrument
        from app.services.risk import exposure_summary

        sectors = {
            i.conid: i.sector for i in (await db.execute(select(Instrument))).scalars().all()
        }
        exposure = exposure_summary(
            live.account, list(live.positions.values()), live.balances, sectors
        )
        daily_pnl = float(live.account.daily_pnl) if live.account.daily_pnl is not None else None
        excess = (
            float(live.account.excess_liquidity)
            if live.account.excess_liquidity is not None
            else None
        )
    fired = await evaluate_rules(
        exposure, daily_pnl, excess, await latest_drawdown_pct(), hub=hub
    )
    return {"fired": fired}
