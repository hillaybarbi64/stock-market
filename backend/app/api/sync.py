"""Sync endpoints: status, manual trigger, reconciliation."""

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import CashTransaction, DailyEquity, Execution, Position, SyncRun
from app.ibkr.types import GatewayState
from app.services import registry

log = get_logger(__name__)
router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/status")
async def sync_status(db: DbSession) -> dict:
    svc = registry.flex_sync
    runs = (
        (await db.execute(select(SyncRun).order_by(desc(SyncRun.started_at)).limit(10)))
        .scalars()
        .all()
    )
    exec_count = (await db.execute(select(func.count()).select_from(Execution))).scalar_one()
    cash_count = (await db.execute(select(func.count()).select_from(CashTransaction))).scalar_one()
    equity_range = (
        await db.execute(select(func.min(DailyEquity.equity_date), func.max(DailyEquity.equity_date)))
    ).one()
    return {
        "configured": bool(svc and svc.is_configured),
        "running": bool(svc and svc._running),
        "totals": {
            "executions": exec_count,
            "cash_transactions": cash_count,
            "equity_days_from": equity_range[0].isoformat() if equity_range[0] else None,
            "equity_days_to": equity_range[1].isoformat() if equity_range[1] else None,
        },
        "runs": [
            {
                "id": r.id,
                "kind": r.kind,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "status": r.status,
                "date_range_from": r.date_range_from,
                "date_range_to": r.date_range_to,
                "records_upserted": r.records_upserted,
                "records_skipped": r.records_skipped,
                "errors": r.errors,
            }
            for r in runs
        ],
    }


_MIN_SECONDS_BETWEEN_RUNS = 90


@router.post("/run")
async def run_sync(db: DbSession) -> dict:
    svc = registry.flex_sync
    if svc is None or not svc.is_configured:
        return {
            "started": False,
            "detail": "Flex אינו מוגדר — יש להזין IBKR_FLEX_TOKEN ו-IBKR_FLEX_QUERY_ID בקובץ .env (ראו RUNBOOK §3)",
        }
    if svc._running:
        return {"started": False, "detail": "סנכרון כבר רץ — המתן שיסתיים (עד ~3 דקות)"}

    # Anti-hammer: IBKR temporarily locks the token (error 1025) after too many
    # rapid attempts. Refuse a new run within 90s of the previous one so a
    # frustrated double/triple-click can't cause that lock.
    last = (
        await db.execute(select(SyncRun).order_by(desc(SyncRun.started_at)).limit(1))
    ).scalar_one_or_none()
    if last is not None:
        ref = last.finished_at or last.started_at
        elapsed = (datetime.now(UTC) - ref).total_seconds() if ref else _MIN_SECONDS_BETWEEN_RUNS
        if elapsed < _MIN_SECONDS_BETWEEN_RUNS:
            return {
                "started": False,
                "detail": f"סנכרון רץ לפני רגע — המתן ~{int(_MIN_SECONDS_BETWEEN_RUNS - elapsed)} שניות "
                "לפני ניסיון נוסף (מונע חסימה זמנית של IBKR).",
            }

    async def _run() -> None:
        try:
            await svc.run(trigger="manual")
        except Exception:  # noqa: BLE001 — recorded on the SyncRun row
            log.exception("manual_sync_failed")

    asyncio.create_task(_run())
    return {"started": True}


@router.get("/reconciliation")
async def reconciliation(db: DbSession) -> dict:
    """Compare live gateway state against locally stored data.
    Discrepancies are reported, never silently fixed."""
    checks: list[dict] = []
    live = registry.live_state

    if live and live.connection.state == GatewayState.CONNECTED and live.account:
        latest_equity = (
            await db.execute(select(DailyEquity).order_by(desc(DailyEquity.equity_date)).limit(1))
        ).scalar_one_or_none()
        if latest_equity and live.account.net_liquidation:
            nav_db = float(latest_equity.nav)
            nav_live = float(live.account.net_liquidation)
            diff_pct = abs(nav_live - nav_db) / nav_db * 100 if nav_db else None
            checks.append(
                {
                    "name": "nav_live_vs_last_daily",
                    "status": "info",
                    "live": nav_live,
                    "stored": nav_db,
                    "stored_date": latest_equity.equity_date.isoformat(),
                    "diff_pct": round(diff_pct, 3) if diff_pct is not None else None,
                    "note": "פער סביר צפוי בתוך יום מסחר; פער גדול מ-5% מול היום האחרון המסונכרן מצדיק בדיקה",
                }
            )

        db_positions = (
            (await db.execute(select(Position).where(Position.is_open.is_(True)))).scalars().all()
        )
        live_conids = {c for c, p in live.positions.items() if p.quantity != 0}
        db_conids = {p.conid for p in db_positions}
        missing_in_db = live_conids - db_conids
        extra_in_db = db_conids - live_conids
        checks.append(
            {
                "name": "positions_live_vs_stored",
                "status": "ok" if not missing_in_db and not extra_in_db else "mismatch",
                "live_count": len(live_conids),
                "stored_count": len(db_conids),
                "missing_in_db": sorted(missing_in_db),
                "extra_in_db": sorted(extra_in_db),
                "note": "פוזיציה החסרה ב-DB תתווסף בעדכון החי הבא; עודף עשוי להעיד על פוזיציה שנסגרה ולא עודכנה",
            }
        )
    else:
        checks.append(
            {
                "name": "gateway",
                "status": "unavailable",
                "note": "אין חיבור חי — השוואה מול Gateway תתאפשר כשהחיבור יחזור",
            }
        )

    exec_gateway_only = (
        await db.execute(
            select(func.count()).select_from(Execution).where(Execution.source == "gateway")
        )
    ).scalar_one()
    checks.append(
        {
            "name": "executions_pending_flex_enrichment",
            "status": "info",
            "count": exec_gateway_only,
            "note": "ביצועים שנקלטו מה-Gateway וממתינים להעשרה מ-Flex (עמלות מדויקות, P&L)",
        }
    )

    return {"checks": checks}
