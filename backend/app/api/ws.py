"""WebSocket endpoint for live UI updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.hub import hub

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            # Client messages are ignored (read-only stream); receiving keeps
            # the connection alive and lets us notice disconnects promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
