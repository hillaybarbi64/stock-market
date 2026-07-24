# ruff: noqa: E402 -- safety env must be set before importing application modules

import asyncio
import os
from urllib.parse import urlparse

# Tests always run against a DEDICATED database, fully isolated from any
# development data. DATABASE_URL from the app container is deliberately
# ignored; Docker/CI must opt into a separate TEST_DATABASE_URL.
test_database_url = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ibkr:ibkr@localhost:5432/ibkr_dashboard_test",
)
if not urlparse(test_database_url).path.removeprefix("/").endswith("_test"):
    raise RuntimeError("Refusing to run tests against a database without an _test suffix")
os.environ["DATABASE_URL"] = test_database_url

# Tests must never contact IBKR or another external provider, even when they
# run inside a container that loaded the real application's .env file.
os.environ["IBKR_FLEX_TOKEN"] = ""
os.environ["IBKR_FLEX_QUERY_ID"] = ""
os.environ["IBKR_FLEX_AUTOSYNC"] = "false"
os.environ["IBKR_GATEWAY_AUTOSTART"] = "false"
os.environ["FINNHUB_API_KEY"] = ""

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
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c
    # Each test runs in its own event loop; the global engine must not leak
    # pooled connections across loops.
    await dispose_engine()
