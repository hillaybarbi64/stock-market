"""Browser-origin guard for local state-changing endpoints."""

import httpx

from app.main import create_app


async def test_cross_origin_post_is_rejected_before_route_execution():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post(
            "/api/sync/run",
            headers={"Origin": "https://malicious.example"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin state change rejected"}


async def test_local_and_non_browser_mutations_are_allowed():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        local = await client.post(
            "/api/system/reconnect",
            headers={"Origin": "http://localhost:3000"},
        )
        no_origin = await client.post("/api/system/reconnect")

    assert local.status_code == 200
    assert no_origin.status_code == 200


async def test_untrusted_host_is_rejected_before_financial_reads():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get(
            "/api/system/connection",
            headers={"Host": "attacker.example"},
        )

    assert response.status_code == 400
