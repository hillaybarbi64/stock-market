"""Exercise real FastAPI startup/shutdown with external providers disabled."""

from app.main import create_app
from app.services import registry


async def test_lifespan_starts_and_cleans_local_services():
    app = create_app()

    async with app.router.lifespan_context(app):
        assert registry.live_state is not None
        assert registry.flex_sync is not None
        assert registry.flex_sync.autosync_enabled is False
        assert registry.supervisor is None

    assert registry.live_state is None
    assert registry.flex_sync is None
    assert registry.supervisor is None
