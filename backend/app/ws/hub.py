"""WebSocket hub: fans out normalized update events to connected UI clients.

Events are small deltas ({"type": "...", "data": {...}, "ts": "..."}), never
full page payloads, so the frontend can merge them without re-rendering
everything. A per-topic throttle prevents flooding the browser.
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

log = get_logger(__name__)


class WsHub:
    def __init__(self, min_interval_s: float = 0.5) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._min_interval_s = min_interval_s
        self._last_sent: dict[str, float] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._flush_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("ws_client_connected", clients=len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("ws_client_disconnected", clients=len(self._clients))

    async def publish(self, topic: str, data: dict[str, Any]) -> None:
        """Publish an event; per-topic throttling keeps only the latest value."""
        now = asyncio.get_event_loop().time()
        last = self._last_sent.get(topic, 0.0)
        if now - last >= self._min_interval_s:
            self._last_sent[topic] = now
            await self._send(topic, data)
        else:
            self._pending[topic] = data
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._flush_later())

    async def _flush_later(self) -> None:
        await asyncio.sleep(self._min_interval_s)
        pending, self._pending = self._pending, {}
        for topic, data in pending.items():
            self._last_sent[topic] = asyncio.get_event_loop().time()
            await self._send(topic, data)

    async def _send(self, topic: str, data: dict[str, Any]) -> None:
        message = json.dumps(
            {"type": topic, "data": data, "ts": datetime.now(UTC).isoformat()},
            default=str,
        )
        async with self._lock:
            clients = list(self._clients)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001 — a dead client must not break the fan-out
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


hub = WsHub()
