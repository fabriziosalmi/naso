from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
import orjson
import aio_pika
import uuid

from shared.core.exceptions import AuthorizationError, ResourceNotFoundError
from shared.database import get_db
from shared.domain.services.darkweb_search import DarkWebSearchService
from shared.domain.services.shodan_search import ShodanService
from shared.domain.services.telegram_search import TelegramOSINTService
from shared.models import LeakHit
from shared.tasks.pipeline import process_potential_leak
from shared.utils.audit import AuditLogger
from shared.utils.reporting import ForensicReportGenerator

from ..deps import get_current_user

router = APIRouter()


class WebhookPayload(BaseModel):
    source: str = Field(..., description="Name of the external tool or script (e.g. 'custom_scraper')")
    content: str = Field(..., description="Raw text or JSON dump discovered")
    metadata: Optional[dict] = Field(default={}, description="Optional tracking tags and OSINT parameters")


@router.post("/ingest/webhook", status_code=202)
async def unified_ingestion_webhook(request: Request, current_user=Depends(get_current_user)):
    """
    ZERO-ALLOCATION WEBHOOK INGESTION (SOTA)
    Reads raw bytes stream via orjson and directly writes to RabbitMQ 
    Celery Queue via aio_pika, bypassing heap allocation buffering.
    """
    from shared.config import settings
    raw_body = await request.body()
    try:
        payload = orjson.loads(raw_body)
    except orjson.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON stream format")

    source = payload.get("source", "webhook")
    content = payload.get("content", "")
    metadata = payload.get("metadata", {})
    metadata["tenant_id"] = current_user.tenant_id

    # 1. Connect to RabbitMQ via aio-pika (Zero-Blocking)
    amqp_url = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@{settings.RABBITMQ_HOST}/"
    connection = await aio_pika.connect_robust(amqp_url)
    
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange("celery", ensure=False) # standard celery exchange
        
        # 2. Celery Protocol v2 JSON Envelope Construction
        task_id = str(uuid.uuid4())
        task_args = ([], {"source": source, "content_snippet": content, "metadata": metadata}, {"callbacks": None, "errbacks": None, "chain": None, "chord": None})
        
        message = aio_pika.Message(
            body=orjson.dumps(task_args),
            content_type="application/json",
            content_encoding="utf-8",
            headers={
                "task": "shared.tasks.pipeline.process_potential_leak",
                "id": task_id,
            },
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(message, routing_key="celery")

    return {
        "status": "accepted",
        "msg": "Payload statically routed via zero-allocation memory pool to Celery Inference Pipeline",
        "tenant_id": current_user.tenant_id,
        "task_id": task_id
    }


@router.get("/recon/darkweb")
async def darkweb_recon(q: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Esegue una ricerca profonda (AA) nel Dark Web tramite Ahmia API.
    """
    results = await DarkWebSearchService.search_onion_links(q)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="DARK_WEB_RECON",
        details={"query": q, "results_count": len(results)},
    )
    await db.commit()
    return results


@router.get("/recon/shodan")
async def shodan_recon(ip: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Esegue una scansione infrastrutturale OSINT tramite Shodan (DD).
    """
    results = await ShodanService.scan_host(ip)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="SHODAN_RECON",
        details={"target_ip": ip, "has_error": "error" in results},
    )
    await db.commit()
    return results


@router.get("/recon/telegram")
async def telegram_recon(channel: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Intercetta il traffico pubblico di un canale Telegram (Threat Actor Chatter).
    """
    results = await TelegramOSINTService.scrape_public_channel(channel)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="TELEGRAM_RECON",
        details={"channel": channel, "results_count": len(results)},
    )
    await db.commit()
    return results


@router.get("/export/dossier")
async def export_massive_dossier(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Genera il Dossier Forense Massivo (BB) per il tenant.
    """
    # 1. Recupera tutti i leak del tenant con join al tenant stesso

    query = (
        select(LeakHit)
        .options(joinedload(LeakHit.tenant))
        .where(LeakHit.tenant_id == current_user.tenant_id)
        .order_by(LeakHit.discovered_at.desc())
    )
    result = await db.execute(query)
    leaks = result.scalars().all()

    if not leaks:
        raise HTTPException(status_code=404, detail="Nessun artefatto leak indicizzato per l'esportazione.")

    tenant_name = leaks[0].tenant.name if leaks[0].tenant else "Unknown Tenant"

    # 2. Generazione PDF Massiva
    pdf_bytes = ForensicReportGenerator.generate_bulk_pdf(tenant_name, leaks)

    # 3. Firma Digitale del Dossier
    signature = ForensicReportGenerator.sign_report(pdf_bytes)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="GENERATE_MASSIVE_DOSSIER",
        details={"leaks_count": len(leaks)},
    )
    await db.commit()

    headers = {"Content-Disposition": 'attachment; filename="NASO-FULL-DOSSIER.pdf"', "X-Forensic-Signature": signature}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.patch("/{leak_id}/status")
async def update_leak_status(
    leak_id: str, status: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Update status and log for compliance (#10).
    """
    result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
    leak = result.scalar_one_or_none()

    if not leak:
        raise ResourceNotFoundError(f"Leak {leak_id} non trovato")

    if current_user.role != "admin" and current_user.tenant_id != leak.tenant_id:
        raise AuthorizationError("Accesso negato")

    old_status = leak.status
    leak.status = status

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="UPDATE_LEAK_STATUS",
        resource_type="leak",
        resource_id=leak_id,
        details={"old_status": old_status, "new_status": status},
    )

    await db.commit()
    return {"status": "updated"}


@router.patch("/{leak_id}/ack")
async def acknowledge_leak(
    leak_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Acknowledge a single critical leak alert.
    """
    result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
    leak = result.scalar_one_or_none()

    if not leak:
        raise ResourceNotFoundError(f"Leak {leak_id} non trovato")

    if current_user.role != "admin" and current_user.tenant_id != leak.tenant_id:
        raise AuthorizationError("Accesso negato")

    from sqlalchemy.sql import func
    leak.acknowledged_at = func.now()
    leak.acknowledged_by = current_user.id

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="ACKNOWLEDGE_LEAK",
        resource_type="leak",
        resource_id=leak_id,
    )

    await db.commit()
    return {"status": "acknowledged", "acknowledged_at": leak.acknowledged_at.isoformat() if leak.acknowledged_at else None}


@router.post("/ack-all")
async def acknowledge_all_critical(
    min_severity: int = 80, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Acknowledge all unacknowledged critical leaks (severity >= min_severity) for the tenant.
    """
    from sqlalchemy.sql import func

    query = select(LeakHit).where(
        LeakHit.severity_score >= min_severity,
        LeakHit.acknowledged_at.is_(None),
    )
    if current_user.role != "admin":
        query = query.where(LeakHit.tenant_id == current_user.tenant_id)

    result = await db.execute(query)
    leaks = result.scalars().all()

    count = 0
    for leak in leaks:
        leak.acknowledged_at = func.now()
        leak.acknowledged_by = current_user.id
        count += 1

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="ACKNOWLEDGE_ALL_CRITICAL",
        resource_type="leak",
        details={"count": count, "min_severity": min_severity},
    )

    await db.commit()
    return {"acknowledged_count": count}


@router.get("/")
async def get_leaks(
    source: Optional[str] = None,
    status: Optional[str] = None,
    min_severity: Optional[int] = None,
    max_severity: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(LeakHit)

    # Multi-tenant isolation (Hardened)
    if current_user.role != "admin":
        query = query.where(LeakHit.tenant_id == current_user.tenant_id)

    if source:
        query = query.where(LeakHit.source.ilike(f"%{source}%"))
    if status:
        query = query.where(LeakHit.status == status)
    if min_severity is not None:
        query = query.where(LeakHit.severity_score >= min_severity)
    if max_severity is not None:
        query = query.where(LeakHit.severity_score <= max_severity)

    result = await db.execute(query.order_by(LeakHit.discovered_at.desc()))
    return result.scalars().all()


@router.get("/{leak_id}/intelligence")
async def get_leak_intelligence(
    leak_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Restituisce i dettagli dell'analisi AI e YARA per un leak specifico.
    """
    result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
    leak = result.scalar_one_or_none()

    if not leak:
        raise ResourceNotFoundError(f"Leak {leak_id} non trovato")

    # Security check (Hardened)
    if current_user.role != "admin" and current_user.tenant_id != leak.tenant_id:
        raise AuthorizationError("Accesso negato al leak del tenant")

    return {
        "id": leak.id,
        "ai_thought": leak.metadata_json.get("ai_thought"),
        "ai_verdict": leak.metadata_json.get("ai_analysis"),
        "severity": leak.severity_score,
    }


@router.get("/{leak_id}/export")
async def export_leak_report(leak_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Genera e scarica un report PDF forense firmato (#31).
    """
    # Fetch leak with tenant info
    result = await db.execute(select(LeakHit).options(joinedload(LeakHit.tenant)).where(LeakHit.id == leak_id))
    leak = result.scalar_one_or_none()

    if not leak:
        raise ResourceNotFoundError(f"Leak {leak_id} non trovato")

    # Security check
    if current_user.role != "admin" and current_user.tenant_id != leak.tenant_id:
        raise AuthorizationError("Accesso negato al leak del tenant")

    # Recupero dati per il report
    ai_analysis = leak.metadata_json.get("ai_analysis", {})
    content = leak.content_snippet or "[RAW CONTENT NOT ACCESSIBLE IN SNIPPET]"
    tenant_name = leak.tenant.name if leak.tenant else "Unknown Tenant"

    # Generazione PDF
    pdf_bytes = ForensicReportGenerator.generate_pdf(
        leak_data={"id": leak.id, "source": leak.source, "discovered_at": leak.discovered_at.isoformat()},
        ai_analysis=ai_analysis,
        content=content,
        tenant_name=tenant_name,
    )

    # Firma (Digital Seal)
    signature = ForensicReportGenerator.sign_report(pdf_bytes)

    headers = {
        "Content-Disposition": f'attachment; filename="NASO-EVIDENCE-{leak_id[:8]}.pdf"',
        "X-Forensic-Signature": signature,
    }

    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/export/data")
async def bulk_export_leaks(
    format: str = "json", db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Export bulk leak data in JSON or CSV format for forensic analysis.
    """
    query = select(LeakHit)
    if current_user.role != "admin":
        query = query.where(LeakHit.tenant_id == current_user.tenant_id)

    result = await db.execute(query.order_by(LeakHit.discovered_at.desc()))
    leaks = result.scalars().all()

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Source", "Severity", "Status", "Timestamp"])
        for l in leaks:
            writer.writerow([l.id, l.source, l.severity_score, l.status, l.discovered_at.isoformat()])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=naso_export.csv"},
        )

    return [
        {
            "id": l.id,
            "source": l.source,
            "severity": l.severity_score,
            "status": l.status,
            "timestamp": l.discovered_at.isoformat(),
            "metadata": l.metadata_json,
        }
        for l in leaks
    ]


@router.get("/{leak_id}/screenshot")
async def get_leak_screenshot(leak_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Recupera lo screenshot forense (W) da MinIO e lo serve all'analista.
    """
    result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
    leak = result.scalar_one_or_none()

    if not leak or not leak.screenshot_path:
        raise ResourceNotFoundError(f"Screenshot non disponibile per il leak {leak_id}")

    if current_user.role != "admin" and current_user.tenant_id != leak.tenant_id:
        raise AuthorizationError("Accesso negato")

    # Proxy da MinIO
    import os

    from minio import Minio

    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")

    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Configurazione MinIO mancante. Ambiente corrotto o compromesso.")

    minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

    # screenshot_path è del tipo minio://bucket/object
    path_parts = leak.screenshot_path.replace("minio://", "").split("/")
    bucket_name = path_parts[0]
    object_name = "/".join(path_parts[1:])

    response = None
    try:
        response = minio_client.get_object(bucket_name, object_name)
        data = response.read()

        # Audit Logging (#10)
        await AuditLogger.log(
            db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            action="VIEW_LEAK_SCREENSHOT",
            resource_type="leak",
            resource_id=leak_id,
        )
        await db.commit()

        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero dello screenshot: {str(e)}")
    finally:
        if response:
            response.close()
            response.release_conn()
