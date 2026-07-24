"""WebSocket endpoint for live UI updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.ws.hub import hub

router = APIRouter()


def websocket_origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    return origin is None or origin in allowed_origins


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    origin = ws.headers.get("origin")
    if not websocket_origin_allowed(origin, get_settings().cors_origins):
        await ws.close(code=1008, reason="Cross-origin WebSocket rejected")
        return
    await hub.connect(ws)
    try:
        while True:
            # Client messages are ignored (read-only stream); receiving keeps
            # the connection alive and lets us notice disconnects promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
