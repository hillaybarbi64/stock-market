"""FastAPI application entrypoint."""

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
    from app.services.live_state import LiveStateService
    from app.ws.hub import hub

    registry.live_state = LiveStateService(hub, settings.snapshot_interval_min)
    if settings.ibkr_gateway_autostart:
        registry.supervisor = GatewaySupervisor(settings, registry.live_state)
        await registry.supervisor.start()
        log.info("gateway_supervisor_started", readonly=True)

    yield

    if registry.supervisor is not None:
        await registry.supervisor.stop()
        registry.supervisor = None
    registry.live_state = None
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
