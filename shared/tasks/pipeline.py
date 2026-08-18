# ruff: noqa: E402
import asyncio
import hashlib
import io
import json
import logging
import os
import time
from datetime import datetime

import httpx
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from shared.celery_app import celery_app
from shared.config import settings
from shared.core.es_client import make_es_client_if_configured
from shared.domain.services.correlation import IdentityCorrelationService
from shared.domain.services.cti_adapters import CTIAdapters
from shared.domain.services.leak_ingest import ingest_leak
from shared.models import YaraRule
from shared.utils.ai_triage import analyze_leak_with_gemma_thinking
from shared.utils.analyzer import analyzer
from shared.utils.babel_node import babel_node
from shared.utils.circuit_breaker import es_breaker, minio_breaker
from shared.utils.worker_tracing import setup_worker_tracing

# Logger Strutturato (#28)
logger = logging.getLogger("naso-pipeline")

# Optional Component Initializations (No hard crashes!)
#
# ES_ENABLED is a marker, NOT a live client. An AsyncElasticsearch built here, at
# import, binds its aiohttp session to the first event loop it runs on; every
# task then runs under a fresh asyncio loop (see the bottom of
# process_potential_leak), so after the first leak the session is bound to a
# closed loop and every subsequent index() fails — swallowed by the circuit
# breaker, so ES indexing simply stopped after the first leak per worker with no
# error surfaced. The client is now built per task, inside store_and_index,
# which runs in the task's own loop.
ES_ENABLED = settings.ES_PASSWORD is not None

if settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY:
    minio_client = Minio(
        settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
else:
    minio_client = None

# Engine for the workers (command side)
# NullPool: every task opens and closes its own connection.
# The standard pool would inherit file descriptors and sockets from the parent (Celery prefork)
# which corrupts the pool — NullPool avoids the problem entirely (G-11).
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args={"prepared_statement_cache_size": 0, "statement_cache_size": 0},
    echo=False,
)
setup_worker_tracing(engine)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# P-01: throttle YARA DB refresh — at most once every 60s per worker process.
# Recompiling YARA on every task wastes CPU proportional to task throughput.
_YARA_REFRESH_INTERVAL: float = 60.0
_last_yara_refresh: float = 0.0

# The SOAR webhook client is created per firing, not at module scope. A
# module-level httpx.AsyncClient binds its connection pool to the loop it first
# runs on; with a fresh loop per task, critical SIEM webhooks stopped firing
# after the first high-severity leak per worker. A critical hit is rare enough
# that paying one TCP+TLS setup when it happens is the right trade against
# silently never alerting.


def generate_idempotency_key(content: str):
    """Build an idempotency key from the hash of the content (#1)."""
    return hashlib.sha256(content.encode()).hexdigest()


@celery_app.task(bind=True)
def process_potential_leak(self, hit_data, raw_content):
    """
    Pipeline SOTA: Idempotency -> Dynamic YARA -> AI Thinking -> Structured Logging -> Circuit Breaker Storage
    Wrapped in a single asyncio.run() to avoid Celery Prefork Deadlocks.
    """
    idempotency_key = generate_idempotency_key(raw_content)
    hit_data["idempotency_key"] = idempotency_key

    async def _run_async_pipeline():
        # 0. Refresh Dynamic YARA Rules — time-gated, max once per 60s (P-01)
        # Avoids recompiling the full YARA ruleset on every single task invocation.
        global _last_yara_refresh
        _now = time.monotonic()
        if _now - _last_yara_refresh >= _YARA_REFRESH_INTERVAL:
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(YaraRule).where(YaraRule.is_active))
                    rules = result.scalars().all()
                    analyzer.refresh_dynamic_rules(rules)  # no-op if ruleset unchanged (P-01)
                _last_yara_refresh = _now
            except Exception as e:
                logger.error(f"Failed to refresh YARA rules: {e}")

        # 1. Babel Node Pre-Processing (NLP & NER)
        try:
            babel_result = babel_node.process_leak(raw_content)
            if "metadata_json" not in hit_data:
                hit_data["metadata_json"] = {}
            hit_data["metadata_json"]["babel"] = babel_result

            # CTI Enrichment on Bitcoin wallets
            btc_wallets = babel_result.get("extracted_entities", {}).get("btc_wallets", [])
            if btc_wallets:
                btc_enrichment = await CTIAdapters.fetch_btc_balance(btc_wallets[0])
                if btc_enrichment:
                    hit_data["metadata_json"]["cti_btc"] = btc_enrichment

            # ThreatFox CTI Enrichment on IP
            ips = babel_result.get("extracted_entities", {}).get("ips", [])
            if ips:
                tf_enrichment = await CTIAdapters.fetch_threatfox_ioc(ips[0])
                if tf_enrichment:
                    hit_data["metadata_json"]["cti_threatfox"] = tf_enrichment

        except Exception as e:
            logger.error(f"[PIPELINE] Babel/CTI pass failed: {e}")

        # 1b. Analisi YARA
        yara_matches, yara_score = analyzer.analyze_text(raw_content)
        if "metadata_json" not in hit_data:
            hit_data["metadata_json"] = {}
        hit_data["metadata_json"]["yara_matches"] = yara_matches
        # Chain of custody: the content digest is already computed as the
        # idempotency key — persist it so the UI and the PDF report can show a
        # real hash instead of inventing one.
        hit_data["metadata_json"]["sha256"] = idempotency_key

        # 2. AI reasoning with a circuit breaker and graceful degradation
        try:
            ai_result = await analyze_leak_with_gemma_thinking(raw_content[:2500])  # P-09: truncate at call site
            # A negative (or unparseable) model verdict must not erase the
            # rule-based evidence: a leak YARA scored 85 stays 85 even when a
            # 2B local model says NO on a truncated snippet. The model can
            # raise severity to the ceiling, never push it below YARA's floor.
            hit_data["severity_score"] = 100 if ai_result["is_valid"] else max(10, yara_score)
            hit_data["metadata_json"]["ai_analysis"] = ai_result
        except Exception as e:
            logger.warning(
                json.dumps(
                    {
                        "event": "ai_degraded",
                        "reason": str(e),
                        "idempotency_key": idempotency_key,
                        "action": "graceful_degradation_active",
                    }
                )
            )
            hit_data["severity_score"] = yara_score

        # 3. Structured Event Logging
        logger.info(
            json.dumps(
                {
                    "event": "leak_processed",
                    "tenant_id": hit_data["tenant_id"],
                    "source": hit_data["source"],
                    "severity": hit_data.get("severity_score", 0),
                    "idempotency_key": idempotency_key,
                }
            )
        )

        # 4. SOAR Integration & Automated Response (SIEM)
        if hit_data.get("severity_score", 0) >= 90:
            try:
                webhook_url = os.getenv("SOAR_WEBHOOK_URL")
                if webhook_url:
                    # Named for what it is. It was called `stix_payload`, and
                    # the README and the docs home page advertised "STIX
                    # profiles" on the strength of that name — but there is no
                    # `type`, no `spec_version`, no `id`, and no SDO or SRO
                    # anywhere in it. A SIEM configured to expect STIX would
                    # reject every one of these. Emitting real STIX 2.1 is a
                    # reasonable thing to want; claiming it because a variable
                    # was named after it is not.
                    soar_payload = {"alert_type": "CRITICAL_OSINT_LEAK", "details": hit_data}
                    async with httpx.AsyncClient(timeout=3.0) as soar_client:
                        await soar_client.post(webhook_url, json=soar_payload)
                    logger.info(f"[SOAR] Fired webhook to SIEM at {webhook_url}")
                else:
                    logger.info("[SOAR] SOAR_WEBHOOK_URL not configured, skipping webhook dispatch")
            except Exception as e:
                logger.error(f"[SOAR] Webhook dispatch failed: {e}")

        # 5. Storage & Indexing with Circuit Breaker
        try:
            await store_and_index(hit_data, raw_content)
        except Exception as e:
            logger.error(json.dumps({"event": "storage_failed", "error": str(e), "idempotency_key": idempotency_key}))
            raise self.retry(exc=e, countdown=60)

        return hit_data["severity_score"]

    # Always create a fresh loop to avoid deadlocking against Celery's prefork pool.
    # asyncio.run() can reuse a loop inherited from the parent process and deadlock.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_async_pipeline())
    finally:
        loop.close()


async def store_and_index(hit_data, raw_content):
    """
    Storage and indexing, guarded by a circuit breaker (#2).
    """
    # P-15: encode once, reuse bytes in both MinIO upload and avoid double-encoding
    content_bytes = raw_content.encode("utf-8")

    # 1. MinIO Storage (Raw Content + Screenshot)
    bucket_name = f"tenant-{hit_data['tenant_id']}"
    object_name = f"{hit_data['idempotency_key']}.txt"
    screenshot_name = f"{hit_data['idempotency_key']}.png"

    async def upload_to_minio():
        if not minio_client:
            raise Exception("MinIO client is disabled")
        screenshot_path = hit_data.get("screenshot_tmp")

        # P-04: MinIO SDK is synchronous blocking — offload to thread pool to free the event loop
        def _sync_upload():
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)
            minio_client.put_object(
                bucket_name, object_name, io.BytesIO(content_bytes), len(content_bytes), content_type="text/plain"
            )
            if screenshot_path and os.path.exists(screenshot_path):
                minio_client.fput_object(bucket_name, screenshot_name, screenshot_path)
                os.remove(screenshot_path)  # Cleanup tmp
                return f"minio://{bucket_name}/{object_name}", f"minio://{bucket_name}/{screenshot_name}"
            return f"minio://{bucket_name}/{object_name}", None

        return await asyncio.get_event_loop().run_in_executor(None, _sync_upload)

    try:
        txt_path, ss_path = await minio_breaker(upload_to_minio)
        hit_data["storage_path"] = txt_path
        hit_data["screenshot_path"] = ss_path
    except Exception as e:
        logger.error(f"[CIRCUIT BREAKER] MinIO storage failed: {e}")
        hit_data["storage_path"] = None
        hit_data["screenshot_path"] = None

    # 2. Elasticsearch Indexing — client built here, in the task's loop.
    if ES_ENABLED:
        es = make_es_client_if_configured()
        es_doc = {
            "tenant_id": hit_data["tenant_id"],
            "source": hit_data["source"],
            "content": raw_content,
            "timestamp": datetime.now().isoformat(),
            "severity": hit_data["severity_score"],
            "metadata": hit_data["metadata_json"],
            "storage_path": hit_data["storage_path"],
        }

        async def index_in_es():
            return await es.index(index="naso-leaks", document=es_doc)

        try:
            await es_breaker(index_in_es)
            logger.info(f"[NASO BATTLE-READY] Leak indexed in ES for tenant {hit_data['tenant_id']}")
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] ES indexing skipped/failed: {e}")
        finally:
            await es.close()
    else:
        logger.warning(f"ES indexing skipped for tenant {hit_data['tenant_id']} (ES disabled)")

    # 3. Persist the LeakHit through the ingest path with fuzzy dedup.
    # ingest_leak:
    #   * populates normalized_content + simhash64 on every write,
    #   * collapses onto an existing row when the Hamming distance is ≤ 3 (a
    #     near-duplicate of a leak already seen, even from a different source
    #     or with slightly different formatting),
    #   * raises the severity monotonically (never downgrades it).
    # Replaces the stable_id=SHA-256(content) pattern, which only caught
    # i duplicati byte-identici.
    async with AsyncSessionLocal() as db:
        leak = await ingest_leak(
            db,
            tenant_id=hit_data["tenant_id"],
            source=hit_data["source"],
            content=raw_content,
            severity_score=hit_data.get("severity_score", 0),
            status="new",
            metadata_json=hit_data.get("metadata_json", {}),
            screenshot_path=hit_data.get("screenshot_path"),
        )
    hit_data["id"] = leak.id

    # 4. Correlazione Identità (Command Side)
    # P-08: pass pre-extracted emails from Babel — skip duplicate full-content regex scan.
    # P-13: pass severity_score and source directly — skip DB re-query in correlate_leak.
    _babel_emails: set = set(
        hit_data.get("metadata_json", {}).get("babel", {}).get("extracted_entities", {}).get("emails", [])
    )
    async with AsyncSessionLocal() as db:
        await IdentityCorrelationService.correlate_leak(
            db,
            leak_id=hit_data["id"],
            content=raw_content,
            tenant_id=hit_data["tenant_id"],
            screenshot_path=hit_data.get("screenshot_path"),
            preextracted_emails=_babel_emails or None,
            severity_score=hit_data.get("severity_score", 0),
            leak_source=hit_data.get("source", "unknown"),
        )

    logger.info(f"[NASO BATTLE-READY] Identity Correlation complete for tenant {hit_data['tenant_id']}")
