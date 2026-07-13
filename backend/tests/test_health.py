async def test_health_reports_components(client):
    resp = await client.get("/api/system/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body["components"]
    assert "ibkr_gateway" in body["components"]
    assert body["uptime_seconds"] >= 0


async def test_health_database_ok(client):
    resp = await client.get("/api/system/health")
    assert resp.json()["components"]["database"]["status"] == "ok"
