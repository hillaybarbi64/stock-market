"""Sync endpoints: status, manual trigger, reconciliation, Flex credentials."""

import asyncio
from collections.abc import Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import db_session, get_db
from app.db.models import CashTransaction, DailyEquity, Execution, Position, SyncRun
from app.ibkr.types import GatewayState
from app.services import registry
from app.services.account_binding import account_binding_exists
from app.services.flex_cooldown import (
    FlexAttemptBlock,
    FlexAttemptBlocked,
    FlexCooldown,
    FlexCooldownActive,
    get_active_flex_cooldown,
    get_flex_attempt_block,
    public_error_details,
)
from app.services.flex_credentials import mask_token, save_flex_credentials
from app.services.flex_sync import SyncAlreadyRunning

log = get_logger(__name__)
router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]
_BACKGROUND_SYNC_TASKS: set[asyncio.Task[None]] = set()


class FlexConfigBody(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    query_id: str = Field(min_length=1, max_length=64)
    run_sync_now: bool = False


@router.get("/flex-config")
async def get_flex_config() -> dict:
    svc = registry.flex_sync
    configured = bool(svc and svc.is_configured)
    return {
        "configured": configured,
        "query_id": svc.query_id if svc and svc.is_configured else "",
        "token_hint": mask_token(svc.token) if svc and svc.is_configured else "",
        "autosync_enabled": bool(svc and svc.autosync_enabled),
    }


@router.put("/flex-config")
async def put_flex_config(body: FlexConfigBody) -> dict:
    """Save Flex credentials (DB) and optionally kick off the first history sync."""
    svc = registry.flex_sync
    if svc is None:
        return {"ok": False, "detail": "Flex sync service not started", "sync_started": False}

    await save_flex_credentials(body.token, body.query_id)
    svc.set_credentials(body.token, body.query_id)

    sync_started = False
    detail = "נשמר. אפשר להריץ סנכרון מהכפתור למעלה."
    if body.run_sync_now and svc.is_configured and svc.is_running:
        detail = "הפרטים נשמרו; סנכרון אחר כבר רץ ולכן לא נשלחה בקשה חדשה."
    elif body.run_sync_now and svc.is_configured:
        async with db_session() as session:
            account_bound = await account_binding_exists(session)
            cooldown = await get_active_flex_cooldown(session)
            attempt_block = await get_flex_attempt_block(session)
        if not account_bound:
            detail = (
                "הפרטים נשמרו, אך לא נשלחה בקשת Flex. "
                "חבר תחילה חשבון יחיד דרך IB Gateway כדי לקשור את ההתקנה."
            )
        elif cooldown:
            detail = _cooldown_detail("הפרטים נשמרו, אך לא נשלחה בקשת Flex.", cooldown)
        elif attempt_block:
            detail = _attempt_block_detail(
                "הפרטים נשמרו, אך לא נשלחה בקשת Flex.",
                attempt_block,
            )
        else:

            async def _run() -> None:
                try:
                    await svc.run(trigger="flex_config_save")
                except FlexCooldownActive as exc:
                    log.info(
                        "flex_config_sync_skipped_cooldown",
                        remaining_s=exc.cooldown.remaining_seconds,
                    )
                except FlexAttemptBlocked as exc:
                    log.info(
                        "flex_config_sync_skipped_attempt_guard",
                        reason=exc.block.reason,
                        remaining_s=exc.block.remaining_seconds,
                    )
                except SyncAlreadyRunning:
                    log.info("flex_config_sync_skipped_running")
                except Exception:  # noqa: BLE001
                    log.exception("flex_config_triggered_sync_failed")

            _start_background_sync(_run())
            sync_started = True
            detail = "נשמר — סנכרון היסטוריה התחיל ברקע (עד כמה דקות)."

    return {
        "ok": True,
        "configured": svc.is_configured,
        "sync_started": sync_started,
        "detail": detail,
        "token_hint": mask_token(svc.token),
        "query_id": svc.query_id,
    }


@router.get("/outbound-ip")
async def outbound_ip() -> dict:
    """Public IP IBKR Flex sees when this backend calls their API (for error 1013)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.ipify.org")
            resp.raise_for_status()
            ip = resp.text.strip()
        return {"ip": ip, "ok": True}
    except Exception as exc:  # noqa: BLE001
        log.warning("outbound_ip_lookup_failed", error=str(exc))
        return {"ip": None, "ok": False, "detail": str(exc)}


@router.get("/status")
async def sync_status(db: DbSession) -> dict:
    svc = registry.flex_sync
    cooldown = await get_active_flex_cooldown(db)
    account_bound = await account_binding_exists(db)
    runs = (
        (await db.execute(select(SyncRun).order_by(desc(SyncRun.started_at)).limit(10)))
        .scalars()
        .all()
    )
    exec_count = (await db.execute(select(func.count()).select_from(Execution))).scalar_one()
    cash_count = (await db.execute(select(func.count()).select_from(CashTransaction))).scalar_one()
    equity_range = (
        await db.execute(
            select(func.min(DailyEquity.equity_date), func.max(DailyEquity.equity_date))
        )
    ).one()

    last_failure = _last_failure_from_runs(list(runs))

    return {
        "configured": bool(svc and svc.is_configured),
        "running": bool(svc and svc.is_running),
        "autosync_enabled": bool(svc and svc.autosync_enabled),
        "account_bound": account_bound,
        "cooldown": _serialize_cooldown(cooldown),
        "last_failure": last_failure,
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
                "errors": public_error_details(r.errors),
            }
            for r in runs
        ],
    }


def _last_failure_from_runs(runs: list[SyncRun]) -> dict | None:
    """Expose a failure only when it is the latest completed Flex outcome."""
    latest_terminal = next(
        (run for run in runs if run.status in {"ok", "failed", "partial"}),
        None,
    )
    if (
        latest_terminal is None
        or latest_terminal.status != "failed"
        or not isinstance(latest_terminal.errors, dict)
    ):
        return None

    from app.ibkr.flex_help import explain_flex_error, help_for_code

    errors = latest_terminal.errors
    public_errors = public_error_details(errors) or {}
    code = errors.get("code") or public_errors.get("error_code")
    err = public_errors.get("error")
    help_he = errors.get("help_he") or help_for_code(str(code) if code else None)
    raw_error = errors.get("error")
    if (not help_he or not code) and isinstance(raw_error, str):
        # Re-derive guidance for legacy rows without returning their raw text.
        derived = explain_flex_error(RuntimeError(raw_error))
        help_he = help_he or derived.get("help_he")
        code = code or derived.get("code")
    return {
        "code": code,
        "error": err,
        "help_he": help_he,
        "started_at": latest_terminal.started_at.isoformat(),
    }


@router.post("/run")
async def run_sync(db: DbSession) -> dict:
    svc = registry.flex_sync
    if svc is None or not svc.is_configured:
        return {
            "started": False,
            "detail": "Flex אינו מוגדר — הזן Token ו-Query ID בטופס למטה (או ב-.env) ואז הרץ סנכרון",
        }
    if svc.is_running:
        return {"started": False, "detail": "סנכרון כבר רץ — המתן שיסתיים (עד ~5 דקות)"}

    if not await account_binding_exists(db):
        return {
            "started": False,
            "detail": (
                "לא נשלחה בקשת Flex. חבר תחילה חשבון יחיד דרך IB Gateway "
                "כדי לקשור את ההתקנה לחשבון הנכון."
            ),
        }

    cooldown = await get_active_flex_cooldown(db)
    if cooldown:
        return {
            "started": False,
            "detail": _cooldown_detail(
                "IBKR חסמה זמנית בקשות Flex ברמת החשבון; לא נשלחה בקשה חדשה.",
                cooldown,
            ),
            "cooldown": _serialize_cooldown(cooldown),
        }

    attempt_block = await get_flex_attempt_block(db)
    if attempt_block:
        return {
            "started": False,
            "detail": _attempt_block_detail(
                "לא נשלחה בקשת Flex חדשה.",
                attempt_block,
            ),
        }

    async def _run() -> None:
        try:
            await svc.run(trigger="manual")
        except FlexCooldownActive as exc:
            log.info("manual_sync_skipped_cooldown", remaining_s=exc.cooldown.remaining_seconds)
        except FlexAttemptBlocked as exc:
            log.info(
                "manual_sync_skipped_attempt_guard",
                reason=exc.block.reason,
                remaining_s=exc.block.remaining_seconds,
            )
        except SyncAlreadyRunning:
            log.info("manual_sync_skipped_running")
        except Exception:  # noqa: BLE001 — recorded on the SyncRun row
            log.exception("manual_sync_failed")

    _start_background_sync(_run())
    return {"started": True}


def _start_background_sync(coroutine: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coroutine, name="flex-manual-sync")
    _BACKGROUND_SYNC_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_SYNC_TASKS.discard)


async def drain_background_sync_tasks() -> None:
    """Cancel and await manual sync jobs before the DB engine is disposed."""
    tasks = list(_BACKGROUND_SYNC_TASKS)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _BACKGROUND_SYNC_TASKS.clear()


def _serialize_cooldown(cooldown: FlexCooldown | None) -> dict:
    if cooldown is None:
        return {
            "active": False,
            "error_code": None,
            "until": None,
            "remaining_seconds": 0,
        }
    return {
        "active": True,
        "error_code": cooldown.error_code,
        "until": cooldown.until.isoformat(),
        "remaining_seconds": cooldown.remaining_seconds,
    }


def _cooldown_detail(prefix: str, cooldown: FlexCooldown) -> str:
    minutes = max(1, (cooldown.remaining_seconds + 59) // 60)
    return f"{prefix} ניסיון יחיד יתאפשר בעוד כ־{minutes} דקות."


def _attempt_block_detail(prefix: str, block: FlexAttemptBlock) -> str:
    if block.reason == "running":
        return (
            f"{prefix} זוהתה ריצה שהתחילה לאחרונה; "
            f"מצב בטוח יתאפשר בעוד כ־{block.remaining_seconds} שניות."
        )
    if block.reason == "interrupted":
        return (
            f"{prefix} סנכרון קודם הופסק בזמן כיבוי; "
            f"ניסיון בטוח יתאפשר בעוד כ־{block.remaining_seconds} שניות."
        )
    return (
        f"{prefix} מרווח הבטיחות מ־IBKR עדיין פעיל; נסה שוב בעוד כ־{block.remaining_seconds} שניות."
    )


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
