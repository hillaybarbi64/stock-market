from fastapi import APIRouter

from app.api import system

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
