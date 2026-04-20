import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.database import get_db
from shared.models import AuditLog

from ..deps import get_current_user

router = APIRouter()


@router.get("/audit", response_model=list[dict])
async def get_audit_logs(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Recupera i log di audit per compliance (#10).
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
