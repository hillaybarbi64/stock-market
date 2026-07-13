import asyncio
import os

# Tests always run against a DEDICATED database, fully isolated from any
# development data. Must be set before app modules import settings.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://ibkr:ibkr@localhost:5432/ibkr_dashboard_test"
os.environ.setdefault("IBKR_FLEX_TOKEN", "")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401 — register models on Base.metadata
from app.db.base import Base, dispose_engine
from app.main import create_app


def _create_schema() -> None:
    async def run() -> None:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(run())


_create_schema()


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Each test runs in its own event loop; the global engine must not leak
    # pooled connections across loops.
    await dispose_engine()
