"""WebSocket requests must obey the same local-origin boundary as REST writes."""

from app.api.ws import websocket_origin_allowed
from app.core.config import Settings


def test_cross_origin_websocket_is_rejected():
    settings = Settings(_env_file=None)

    assert websocket_origin_allowed("http://localhost:3000", settings.cors_origins)
    assert websocket_origin_allowed(None, settings.cors_origins)
    assert not websocket_origin_allowed("https://malicious.example", settings.cors_origins)
