import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.config import settings
from shared.database import get_db
from shared.models import AuditLog
from shared.utils.audit_chain import verify_chain

from ..deps import get_current_user

logger = logging.getLogger("naso-core")

router = APIRouter()


@router.get("/audit", response_model=list[dict])
async def get_audit_logs(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Return the audit log for compliance purposes (#10).
    """
    query = select(AuditLog)
    if current_user.role != "admin":
        query = query.where(AuditLog.tenant_id == current_user.tenant_id)

    result = await db.execute(query.order_by(AuditLog.timestamp.desc()).limit(100))
    logs = result.scalars().all()

    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "timestamp": l.timestamp.isoformat(),
            "details": l.details,
        }
        for l in logs
    ]


@router.get("/audit/verify")
async def verify_audit_chain_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Run :func:`verify_chain` over the operator's tenant and report the
    outcome. Non-admins are pinned to their own tenant; admins can pass
    ``?tenant_id=...`` to verify a specific customer's chain.

    Response: ``{ok, broken_at, reason, total}`` — ``total`` gives the
    operator a sense of how long a chain was verified without having to
    hit the raw audit endpoint.
    """
    tenant_id = current_user.tenant_id
    result = await verify_chain(db, tenant_id=tenant_id)

    # Count rows for UX — "verified 247 entries, chain intact".
    count_stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    total = len((await db.execute(count_stmt)).scalars().all())

    return {
        "ok": result.ok,
        "broken_at": result.broken_at,
        "reason": result.reason,
        "total": total,
        "tenant_id": tenant_id,
    }


@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)):
    try:
        start_time = time.perf_counter()
        await db.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {"status": "operational", "latency_ms": {"total": round(elapsed_ms, 2)}}
    except Exception:
        # Never expose internal detail (connection string, stack trace, DB hostname)
        # to the client — return a generic status to avoid information disclosure.
        # It still has to be logged: a silently swallowed exception meant a
        # degraded API could not explain itself to its own operator.
        logger.exception("System status probe failed")
        return {"status": "degraded", "latency_ms": {"total": -1}}


# ── Composite health ────────────────────────────────────────────────────────
#
# /status answers one question — can the API reach its database — because that
# is what a container HEALTHCHECK should gate on. /health answers the operator's
# question: which of the five backing services is actually up.
#
# Deliberately unauthenticated, and deliberately terse. Each component reports
# "ok", "degraded" or "disabled" and a latency, and nothing else: no hostnames,
# no versions, no exception text. An unauthenticated endpoint that says
# "elasticsearch at es-prod-04.internal: ConnectionRefused" is a free network
# map for whoever finds it. Detail goes to the log, where it belongs.

_HEALTH_PROBE_TIMEOUT = 3.0


async def _timed(name: str, probe):
    """Run one probe under a timeout and reduce it to (status, latency_ms)."""
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(probe(), timeout=_HEALTH_PROBE_TIMEOUT)
    except Exception:
        logger.exception("Health probe failed: %s", name)
        return name, {"status": "degraded", "latency_ms": -1}
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    if result is None:
        # The component is not configured in this deployment. Not an error:
        # Elasticsearch and MinIO are optional, and reporting them as degraded
        # would make a correct minimal install look broken forever.
        return name, {"status": "disabled", "latency_ms": None}
    return name, {"status": "ok", "latency_ms": elapsed}


async def _probe_database(db: AsyncSession):
    await db.execute(text("SELECT 1"))
    return True


async def _probe_redis():
    import redis.asyncio as redis

    client = redis.from_url(settings.REDIS_HOST, decode_responses=True)
    try:
        await client.ping()
        return True
    finally:
        await client.aclose()


async def _probe_elasticsearch():
    if not settings.ES_PASSWORD:
        return None
    from elasticsearch import AsyncElasticsearch

    es = AsyncElasticsearch(
        f"https://elastic:{settings.ES_PASSWORD}@{settings.ES_HOST}:{settings.ES_PORT}",
        verify_certs=False,
    )
    try:
        await es.ping()
        return True
    finally:
        await es.close()


async def _probe_minio():
    if not (settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY):
        return None
    from minio import Minio

    client = Minio(
        settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    # minio's SDK is synchronous; keep it off the event loop.
    await asyncio.to_thread(client.list_buckets)
    return True


async def _probe_rabbitmq():
    # No AMQP round trip: opening a broker connection per health check is
    # expensive and the management API is not always exposed. A TCP handshake
    # to the AMQP port distinguishes "broker down" from "broker up", which is
    # the question being asked.
    _, writer = await asyncio.open_connection(settings.RABBITMQ_HOST, 5672)
    writer.close()
    await writer.wait_closed()
    return True


@router.get("/health")
async def get_health(response: Response, db: AsyncSession = Depends(get_db)):
    """Composite readiness across every backing service.

    Answers 200 when everything configured is reachable and 503 when anything
    is not, so a load balancer can act on it without parsing the body. The body
    still carries the per-component breakdown for a human.
    """
    probes = [
        _timed("database", lambda: _probe_database(db)),
        _timed("redis", _probe_redis),
        _timed("elasticsearch", _probe_elasticsearch),
        _timed("minio", _probe_minio),
        _timed("rabbitmq", _probe_rabbitmq),
    ]
    components = dict(await asyncio.gather(*probes))

    degraded = [name for name, c in components.items() if c["status"] == "degraded"]
    overall = "degraded" if degraded else "operational"
    if degraded:
        response.status_code = 503

    return {"status": overall, "components": components, "degraded": degraded}
