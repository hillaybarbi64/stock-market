from fastapi import APIRouter

from app.api import account, performance, positions, sync, system, ws

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])
api_router.include_router(ws.router, tags=["ws"])
