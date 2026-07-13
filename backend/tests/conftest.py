import os

# Test configuration must be set before app modules import settings.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://ibkr:ibkr@localhost:5432/ibkr_dashboard"
)
os.environ.setdefault("IBKR_FLEX_TOKEN", "")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import dispose_engine
from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Each test runs in its own event loop; the global engine must not leak
    # pooled connections across loops.
    await dispose_engine()
