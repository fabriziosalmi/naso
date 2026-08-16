import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.database import get_db
from shared.models import AuditLog
from shared.utils.audit_chain import verify_chain

from ..deps import get_current_user

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
        return {"status": "degraded", "latency_ms": {"total": -1}}
