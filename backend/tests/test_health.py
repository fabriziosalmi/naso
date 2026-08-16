"""Tests for /system/health, the composite readiness endpoint.

The suite has no Redis, RabbitMQ, Elasticsearch or MinIO, so the probes are
patched. What is worth pinning is the endpoint's contract rather than any one
probe's mechanics:

  * everything reachable -> 200 and "operational";
  * anything unreachable -> 503, with the failing component named;
  * an unconfigured optional component -> "disabled", not "degraded";
  * the body never carries an exception message or a hostname.
"""

import pytest
from app.api.endpoints import system


@pytest.fixture
def stub_probes(monkeypatch):
    """Replace every non-database probe with a controllable stub."""

    async def ok():
        return True

    for name in ("_probe_redis", "_probe_elasticsearch", "_probe_minio", "_probe_rabbitmq"):
        monkeypatch.setattr(system, name, ok)
    return monkeypatch


@pytest.mark.asyncio
async def test_all_components_reachable(client, stub_probes):
    r = await client.get("/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "operational"
    assert body["degraded"] == []
    assert set(body["components"]) == {"database", "redis", "elasticsearch", "minio", "rabbitmq"}
    assert all(c["status"] == "ok" for c in body["components"].values())


@pytest.mark.asyncio
async def test_one_dead_component_answers_503(client, stub_probes):
    async def boom():
        raise ConnectionRefusedError("redis-prod-01.internal:6379 refused")

    stub_probes.setattr(system, "_probe_redis", boom)

    r = await client.get("/system/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["degraded"] == ["redis"]
    assert body["components"]["redis"]["status"] == "degraded"
    assert body["components"]["redis"]["latency_ms"] == -1
    # The database is unaffected and must still read as healthy.
    assert body["components"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_failure_detail_is_not_leaked_to_the_client(client, stub_probes):
    async def boom():
        raise ConnectionRefusedError("es-prod-04.internal:9200 refused")

    stub_probes.setattr(system, "_probe_elasticsearch", boom)

    r = await client.get("/system/health")
    assert "internal" not in r.text
    assert "ConnectionRefused" not in r.text


@pytest.mark.asyncio
async def test_unconfigured_optional_component_is_disabled_not_degraded(client, stub_probes):
    async def not_configured():
        return None

    stub_probes.setattr(system, "_probe_minio", not_configured)

    r = await client.get("/system/health")
    assert r.status_code == 200
    assert r.json()["components"]["minio"] == {"status": "disabled", "latency_ms": None}


@pytest.mark.asyncio
async def test_a_hanging_probe_does_not_hang_the_endpoint(client, stub_probes):
    import asyncio

    async def hang():
        await asyncio.sleep(60)

    stub_probes.setattr(system, "_probe_rabbitmq", hang)
    stub_probes.setattr(system, "_HEALTH_PROBE_TIMEOUT", 0.05)

    r = await client.get("/system/health")
    assert r.status_code == 503
    assert r.json()["components"]["rabbitmq"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_needs_no_authentication(client, stub_probes):
    # An orchestrator probing this endpoint has no credentials. If this ever
    # starts returning 401 the deployment silently stops being health-checked.
    assert (await client.get("/system/health")).status_code == 200
