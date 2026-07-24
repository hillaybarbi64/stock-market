"""System endpoints: health, status, version."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_db
from app.services import registry

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter()

_started_at = datetime.now(UTC)


@router.get("/connection")
async def connection_status() -> dict:
    """Live IBKR connection state for the status strip and system page."""
    from app.services.live_state import _connection_payload

    live = registry.live_state
    if live is None:
        return {"state": "disconnected", "readonly": True, "detail": "service not started"}
    payload = _connection_payload(live.connection)
    gateway_port = get_settings().ibkr_gateway_port
    payload["gateway_port"] = gateway_port
    payload["account_mode"] = "paper" if gateway_port in {4002, 7497} else "live"
    supervisor = registry.supervisor
    confirmation_required = bool(supervisor and supervisor.binding_confirmation_required)
    payload["account_binding_confirmation_required"] = confirmation_required
    payload["account_binding_confirmation_id"] = (
        supervisor.binding_confirmation_id if supervisor and confirmation_required else None
    )
    return payload


@router.post("/reconnect")
async def manual_reconnect() -> dict:
    """User-triggered reconnect: skips the current backoff wait."""
    if registry.supervisor is None:
        return {"ok": False, "detail": "gateway supervisor not running"}
    await registry.supervisor.manual_reconnect()
    return {"ok": True}


class AccountBindingConfirmationBody(BaseModel):
    confirmation_id: str = Field(min_length=16, max_length=128)


@router.post("/confirm-account-binding")
async def confirm_pending_account_binding(body: AccountBindingConfirmationBody) -> dict:
    """Explicit one-time binding for an upgraded database with existing rows."""
    supervisor = registry.supervisor
    if supervisor is None:
        return {"ok": False, "detail": "אין חשבון ממתין לאישור."}

    from app.ibkr.gateway import mask_account
    from app.services.account_binding import confirm_account_binding

    account_id = supervisor.pending_account_for_confirmation(body.confirmation_id)
    if not account_id:
        return {
            "ok": False,
            "detail": "האישור פג או שהחשבון השתנה. בדוק שוב את המספר הממוסך.",
        }

    await confirm_account_binding(account_id)
    supervisor.complete_binding_confirmation(body.confirmation_id, account_id)
    await supervisor.manual_reconnect()
    return {
        "ok": True,
        "detail": f"ההתקנה נקשרה לחשבון {mask_account(account_id)}.",
    }


class ComponentHealth(BaseModel):
    status: str  # ok | degraded | down
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float
    components: dict[str, ComponentHealth]


@router.get("/health", response_model=HealthResponse)
async def health(db: DbSession) -> HealthResponse:
    settings = get_settings()
    components: dict[str, ComponentHealth] = {}

    try:
        await db.execute(text("SELECT 1"))
        components["database"] = ComponentHealth(status="ok")
    except Exception as exc:  # noqa: BLE001 — health must never raise
        components["database"] = ComponentHealth(status="down", detail=type(exc).__name__)

    live = registry.live_state
    if live is None:
        components["ibkr_gateway"] = ComponentHealth(status="down", detail="not_started")
    else:
        state = live.connection.state.value
        components["ibkr_gateway"] = ComponentHealth(
            status="ok" if state == "connected" else "down",
            detail=state if state != "connected" else None,
        )

    overall = "ok" if components["database"].status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=(datetime.now(UTC) - _started_at).total_seconds(),
        components=components,
    )
