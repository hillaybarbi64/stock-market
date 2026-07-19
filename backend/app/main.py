"""FastAPI application entrypoint."""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import dispose_engine, get_engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    get_engine()
    log.info("startup", app=settings.app_name, version=settings.app_version)

    from app.ibkr.gateway import GatewaySupervisor
    from app.services import registry
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
            log.info("flex_credentials_loaded_from_db", query_id=db_query_id)
    except Exception:  # noqa: BLE001 — never block boot on optional settings row
        log.exception("flex_credentials_load_failed")

    # Flex history sync is independent of the live Gateway connection.
    sync_loop_task = asyncio.create_task(daily_sync_loop(registry.flex_sync))

    if settings.ibkr_gateway_autostart:
        registry.supervisor = GatewaySupervisor(settings, registry.live_state)
        await registry.supervisor.start()
        log.info("gateway_supervisor_started", readonly=True)

    try:
        yield
    finally:
        sync_loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sync_loop_task
        if registry.supervisor is not None:
            with contextlib.suppress(Exception):
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
