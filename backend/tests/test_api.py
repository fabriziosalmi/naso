import pytest

@pytest.mark.asyncio
async def test_read_system_status(client):
    response = await client.get("/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "latency_ms" in data

@pytest.mark.asyncio
async def test_auth_protected_route(client):
    # Should fail without token
    response = await client.get("/leaks/")
    assert response.status_code == 401
