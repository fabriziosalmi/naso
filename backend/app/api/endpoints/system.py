import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.config import settings
from shared.database import get_db
from shared.models import AuditLog
from shared.utils.audit_chain import verify_chain

from ..deps import get_current_user

router = APIRouter()
logger = logging.getLogger("naso-health")

# Per-probe timeout. Health checks must not block the request; if a
# backend is wedged we'd rather report "degraded" within a second than
# hang the load balancer.
_HEALTH_TIMEOUT_SECONDS = 1.0


async def _timed(coro) -> dict:
    """Run *coro* under a hard timeout and return a status dict.

    Never raises: wraps every exception into ``{ok=False, error=...}``
    so ``asyncio.gather`` doesn't have to ferry exceptions back up. The
    error payload is opaque ("unreachable" / "timeout") to avoid leaking
    internal hostnames or error message contents to unauthenticated
    clients hitting /system/health.
    """
    started = time.perf_counter()
    try:
        await asyncio.wait_for(coro, timeout=_HEALTH_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return {"ok": False, "latency_ms": int(_HEALTH_TIMEOUT_SECONDS * 1000), "error": "timeout"}
    except Exception as exc:
        logger.warning("health probe failed: %s", exc)
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "unreachable",
        }
    return {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}


async def _check_db(db: AsyncSession) -> None:
    await db.execute(text("SELECT 1"))


async def _check_redis() -> None:
    # Reuse the singleton blacklist client — it's already connected and
    # gives us a guaranteed round-trip against the same Redis instance
    # the auth path depends on.
    from shared.core.jwt_manager import jwt_blacklist  # noqa: PLC0415

    client = await jwt_blacklist.get_client()
    await client.ping()


async def _check_rabbitmq() -> None:
    from ...infrastructure.rabbitmq import rabbitmq_pool  # noqa: PLC0415

    channel = await rabbitmq_pool.get_channel()
    try:
        # Just acquiring a channel proves the broker is reachable and
        # auth-validated. Don't actually publish anything.
        return
    finally:
        await channel.close()


async def _check_minio() -> None:
    if not settings.MINIO_ACCESS_KEY:
        raise RuntimeError("not configured")
    from minio import Minio  # noqa: PLC0415

    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    # Minio SDK is sync; offload to the default thread pool so we don't
    # block the event loop on a slow I/O.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, client.list_buckets)


async def _check_elasticsearch() -> None:
    if not settings.ES_PASSWORD:
        raise RuntimeError("not configured")
    from elasticsearch import AsyncElasticsearch  # noqa: PLC0415

    es = AsyncElasticsearch(
        f"https://elastic:{settings.ES_PASSWORD}@{settings.ES_HOST}:{settings.ES_PORT}",
        verify_certs=settings.ES_VERIFY_CERTS,
    )
    try:
        if not await es.ping():
            raise RuntimeError("ping returned false")
    finally:
        await es.close()


@router.get("/audit")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, max_length=255),
    resource_type: str | None = Query(None, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Paginated audit-log read.

    Query params:
      * ``limit`` — page size, [1..500], default 100. Avoids hammering
        the DB with a SELECT * when /audit is hit by a script.
      * ``offset`` — straight numeric offset for keyset pagination.
        Cursor-based pagination is a follow-up; for now offset is
        bounded enough by the limit cap.
      * ``action`` and ``resource_type`` — optional equality filters.
        Useful to drill into a class of events ("show me every
        IDENTITY_MERGED") without pulling the full table.

    Response shape: ``{total, limit, offset, items: [...]}`` so the
    client can render "showing 100 of 4321".
    """
    base = select(AuditLog)
    if current_user.role != "admin":
        base = base.where(AuditLog.tenant_id == current_user.tenant_id)
    if action:
        base = base.where(AuditLog.action == action)
    if resource_type:
        base = base.where(AuditLog.resource_type == resource_type)

    # Total count — proper aggregate, not len(all_rows).
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Page rows.
    rows = (
        await db.execute(base.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit))
    ).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "timestamp": l.timestamp.isoformat(),
                "details": l.details,
            }
            for l in rows
        ],
    }


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
    # Use a proper SQL aggregate; the previous len(all_rows) materialized
    # the entire chain into Python memory just to count it, which is
    # quadratic with how often the integrity banner re-runs verify.
    count_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == tenant_id)
    total = (await db.execute(count_stmt)).scalar_one()

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
        # Non esponiamo mai dettagli interni (connection string, stacktrace, hostname DB)
        # al client — solo uno stato generico per evitare information disclosure.
        return {"status": "degraded", "latency_ms": {"total": -1}}


@router.get("/health")
async def get_health(db: AsyncSession = Depends(get_db)):
    """Composite liveness/readiness probe.

    Pings every backing service in parallel under a 1 s cap. Postgres
    and Redis are critical — if either is unreachable the whole
    response flips to "down". The other three (RabbitMQ, MinIO, ES)
    drop overall status to "degraded" but the API can still serve
    cached identity data and basic auth.

    No auth: load balancers and orchestrators (Kubernetes liveness,
    docker compose healthcheck) need to call this without credentials.
    The response intentionally never carries hostnames, ports, or raw
    exception strings — just opaque "unreachable" / "timeout".
    """
    db_check, redis_check, rmq_check, minio_check, es_check = await asyncio.gather(
        _timed(_check_db(db)),
        _timed(_check_redis()),
        _timed(_check_rabbitmq()),
        _timed(_check_minio()),
        _timed(_check_elasticsearch()),
    )

    services = {
        "postgres": db_check,
        "redis": redis_check,
        "rabbitmq": rmq_check,
        "minio": minio_check,
        "elasticsearch": es_check,
    }
    critical_ok = db_check["ok"] and redis_check["ok"]
    if not critical_ok:
        overall = "down"
    elif not all(s["ok"] for s in services.values()):
        overall = "degraded"
    else:
        overall = "ok"
    return {"status": overall, "services": services}
