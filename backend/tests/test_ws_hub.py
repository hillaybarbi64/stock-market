"""WsHub throttling: rapid updates on one topic collapse to first + latest."""

import asyncio
import json

from app.ws.hub import WsHub


class FakeWs:
    def __init__(self):
        self.sent: list[str] = []

    async def accept(self):
        pass

    async def send_text(self, text: str):
        self.sent.append(text)


async def test_publish_throttles_per_topic():
    hub = WsHub(min_interval_s=0.05)
    ws = FakeWs()
    await hub.connect(ws)  # type: ignore[arg-type]

    for i in range(10):
        await hub.publish("price", {"v": i})
    await asyncio.sleep(0.12)

    values = [json.loads(m)["data"]["v"] for m in ws.sent]
    assert values[0] == 0  # first goes out immediately
    assert values[-1] == 9  # latest wins after the throttle window
    assert len(values) < 10  # intermediate updates were collapsed


async def test_dead_client_is_removed():
    hub = WsHub(min_interval_s=0.01)

    class DeadWs(FakeWs):
        async def send_text(self, text: str):
            raise RuntimeError("gone")

    dead = DeadWs()
    await hub.connect(dead)  # type: ignore[arg-type]
    await hub.publish("x", {"v": 1})
    assert dead not in hub._clients
