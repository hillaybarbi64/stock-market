"""FastAPI application entrypoint."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import dispose_engine, get_engine

log = get_logger(__name__)
_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    get_engine()
    log.info("startup", app=settings.app_name, version=settings.app_version)

    from app.ibkr.gateway import GatewaySupervisor
    from app.services import registry
    from app.services.account_binding import ensure_account_binding
    from app.services.flex_sync import FlexSyncService
    from app.services.live_state import LiveStateService
    from app.services.scheduler import daily_sync_loop
    from app.ws.hub import hub

    registry.live_state = LiveStateService(hub, settings.snapshot_interval_min)
    registry.flex_sync = FlexSyncService(settings)
    from app.services.flex_credentials import load_flex_credentials
    from app.services.templates import ensure_builtin_templates

    await ensure_builtin_templates()
    # UI-saved Flex credentials override empty/stale env values.
    try:
        db_token, db_query_id = await load_flex_credentials()
        if db_token and db_query_id:
            registry.flex_sync.set_credentials(db_token, db_query_id)
            log.info("flex_credentials_loaded_from_db")
    except Exception:  # noqa: BLE001 — never block boot on optional settings row
        log.exception("flex_credentials_load_failed")

    # Flex history sync is independent of the live Gateway connection, but is
    # opt-in so a backend restart can never submit a report unexpectedly.
    sync_loop_task: asyncio.Task | None = None
    if settings.ibkr_flex_autosync:
        sync_loop_task = asyncio.create_task(daily_sync_loop(registry.flex_sync))
        log.info("flex_autosync_enabled")
    else:
        log.info("flex_autosync_disabled")

    if settings.ibkr_gateway_autostart:
        registry.supervisor = GatewaySupervisor(
            settings,
            registry.live_state,
            account_guard=ensure_account_binding,
        )
        await registry.supervisor.start()
        log.info("gateway_supervisor_started", readonly=True)

    try:
        yield
    finally:
        if sync_loop_task is not None:
            sync_loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await sync_loop_task
        from app.api.sync import drain_background_sync_tasks

        await drain_background_sync_tasks()
        if registry.supervisor is not None:
            with suppress(Exception):
                await registry.supervisor.stop()
            registry.supervisor = None
        registry.live_state = None
        registry.flex_sync = None
        await dispose_engine()
        log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="IBKR Dashboard API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    # Reject DNS-rebinding hosts before any financial read endpoint is served.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_cross_origin_mutations(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in _STATE_CHANGING_METHODS
            and origin
            and origin not in settings.cors_origins
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin state change rejected"},
            )
        return await call_next(request)

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
