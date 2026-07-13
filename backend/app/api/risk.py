"""Risk & insights endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Insight, Instrument
from app.ibkr.types import GatewayState
from app.services import registry
from app.services.insights import (
    behavior_insights,
    concentration_insights,
    fx_imbalance_insight,
    margin_insight,
)
from app.services.risk import exposure_summary, stress_scenarios

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _exposure(db: AsyncSession):
    live = registry.live_state
    if not live or not live.account:
        return None, True
    sectors = {
        i.conid: i.sector
        for i in (await db.execute(select(Instrument))).scalars().all()
    }
    stale = live.connection.state != GatewayState.CONNECTED
    return (
        exposure_summary(live.account, list(live.positions.values()), live.balances, sectors),
        stale,
    )


@router.get("/summary")
async def risk_summary(db: DbSession) -> dict:
    exp, stale = await _exposure(db)
    if exp is None:
        return {
            "available": False,
            "detail": "אין נתוני חשבון חיים או שמורים — נדרש חיבור Gateway ראשון.",
        }
    return {
        "available": True,
        "stale": stale,
        "source": "ibkr_gateway" if not stale else "last_known_state",
        "exposure": exp.__dict__,
        "scenarios": stress_scenarios(exp),
        "notes": [
            "תרחישי הקיצון הם חישוב פרמטרי שקוף — לא תחזית.",
            "קורלציות ובטא פר-פוזיציה יחושבו כשתסונכרן היסטוריית מחירים לנכסים (עמוד סנכרון).",
        ],
    }


@router.post("/insights/refresh")
async def refresh_insights(db: DbSession) -> dict:
    exp, _stale = await _exposure(db)
    drafts = []
    if exp is not None:
        live = registry.live_state
        balances_summary = [
            {
                "currency": b.currency,
                "cash": float(b.cash_balance),
                "cash_in_base": float(b.cash_balance * (b.fx_rate_to_base or 1)),
            }
            for b in (live.balances if live else [])
        ]
        drafts += concentration_insights(exp)
        drafts += fx_imbalance_insight(exp, balances_summary)
        drafts += margin_insight(exp)
    drafts += await behavior_insights(db)

    existing_titles = {
        i.title
        for i in (
            await db.execute(select(Insight).where(Insight.dismissed_at.is_(None)))
        ).scalars()
    }
    created = 0
    for d in drafts:
        if d.title in existing_titles:
            continue
        db.add(
            Insight(
                kind=d.kind,
                severity=d.severity,
                confidence=d.confidence,
                title=d.title,
                body=d.body,
                evidence=d.evidence,
                assumptions=d.assumptions,
                links={"page": d.link} if d.link else None,
                created_at=datetime.now(UTC),
            )
        )
        created += 1
    await db.commit()
    return {"generated": len(drafts), "new": created}


@router.get("/insights")
async def list_insights(db: DbSession, include_dismissed: bool = False) -> dict:
    q = select(Insight).order_by(desc(Insight.created_at))
    if not include_dismissed:
        q = q.where(Insight.dismissed_at.is_(None))
    rows = (await db.execute(q)).scalars().all()
    return {
        "insights": [
            {
                "id": i.id,
                "kind": i.kind,
                "severity": i.severity,
                "confidence": i.confidence,
                "title": i.title,
                "body": i.body,
                "evidence": i.evidence,
                "assumptions": i.assumptions,
                "links": i.links,
                "created_at": i.created_at.isoformat(),
                "dismissed_at": i.dismissed_at.isoformat() if i.dismissed_at else None,
            }
            for i in rows
        ]
    }


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(insight_id: int, db: DbSession) -> dict:
    insight = await db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(404, "insight not found")
    insight.dismissed_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}
