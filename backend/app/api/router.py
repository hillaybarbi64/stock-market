from fastapi import APIRouter

from app.api import account, journal, performance, positions, risk, sync, system, trades, ws

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(journal.router, prefix="/journal", tags=["journal"])
api_router.include_router(risk.router, prefix="/risk", tags=["risk"])
api_router.include_router(ws.router, tags=["ws"])
