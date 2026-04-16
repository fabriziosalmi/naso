# ruff: noqa: E402
from shared.celery_app import celery_app
from shared.utils.analyzer import analyzer
from shared.utils.ai_triage import analyze_leak_with_gemma_thinking
from shared.models import YaraRule
from sqlalchemy import select
import asyncio
import os
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from minio import Minio
import io

# Setup asincrono per ES
ES_HOST = os.getenv("ES_HOST", "elasticsearch")
ES_PASSWORD = os.getenv("ELASTIC_PASSWORD")
if not ES_PASSWORD:
    raise ValueError("CRITICAL: ELASTIC_PASSWORD environment variable is missing!")
es = AsyncElasticsearch(f"https://elastic:{ES_PASSWORD}@{ES_HOST}:9200", verify_certs=False)

# Setup MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
    raise ValueError("CRITICAL: MINIO credentials missing!")
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

from shared.utils.circuit_breaker import es_breaker, minio_breaker
import hashlib
import json
import logging
from shared.domain.services.correlation import IdentityCorrelationService
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from shared.utils.worker_tracing import setup_worker_tracing
from shared.utils.babel_node import babel_node
from shared.domain.services.cti_adapters import CTIAdapters

# Logger Strutturato (#28)
logger = logging.getLogger("naso-pipeline")

# Engine per i worker (Command Side)
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("CRITICAL: DATABASE_URL environment variable is missing!")
engine = create_async_engine(
    DB_URL,
    pool_size=int(os.getenv("WORKER_DB_POOL_SIZE", 20)),
    max_overflow=int(os.getenv("WORKER_DB_MAX_OVERFLOW", 50)),
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "prepared_statement_cache_size": 250,
        "statement_cache_size": 500
    },
    echo=False
)
setup_worker_tracing(engine)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def generate_idempotency_key(content: str):
    """Genera una chiave di idempotenza basata sull'hash del contenuto (#1)."""
    return hashlib.sha256(content.encode()).hexdigest()

@celery_app.task(bind=True)
def process_potential_leak(self, hit_data, raw_content):
    """
    Pipeline SOTA: Idempotency -> Dynamic YARA -> AI Thinking -> Structured Logging -> Circuit Breaker Storage
    """
    idempotency_key = generate_idempotency_key(raw_content)
    hit_data["idempotency_key"] = idempotency_key
    
    # 0. Refresh Dynamic YARA Rules (#25)
    async def refresh_yara():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(YaraRule).where(YaraRule.is_active))
            rules = result.scalars().all()
            analyzer.refresh_dynamic_rules(rules)
            
    try:
        asyncio.run(refresh_yara())
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
            btc_enrichment = asyncio.run(CTIAdapters.fetch_btc_balance(btc_wallets[0])) # Limit to top hit for speed
            if btc_enrichment:
                hit_data["metadata_json"]["cti_btc"] = btc_enrichment
                
        # ThreatFox CTI Enrichment on IP
        ips = babel_result.get("extracted_entities", {}).get("ips", [])
        if ips:
            tf_enrichment = asyncio.run(CTIAdapters.fetch_threatfox_ioc(ips[0]))
            if tf_enrichment:
                hit_data["metadata_json"]["cti_threatfox"] = tf_enrichment
                
    except Exception as e:
        logger.error(f"[PIPELINE] Babel/CTI pass failed: {e}")

    # 1. Analisi YARA
    yara_matches, yara_score = analyzer.analyze_text(raw_content)
    if "metadata_json" not in hit_data:
        hit_data["metadata_json"] = {}
    hit_data["metadata_json"]["yara_matches"] = yara_matches
    
    # 2. AI Thinking con Circuit Breaker e Graceful Degradation
    try:
        ai_result = asyncio.run(analyze_leak_with_gemma_thinking(raw_content))
        hit_data["severity_score"] = 100 if ai_result["is_valid"] else 10
        hit_data["metadata_json"]["ai_analysis"] = ai_result
    except Exception as e:
        logger.warning(json.dumps({
            "event": "ai_degraded",
            "reason": str(e),
            "idempotency_key": idempotency_key,
            "action": "graceful_degradation_active"
        }))
        hit_data["severity_score"] = yara_score

    # 3. Structured Event Logging (#28)
    logger.info(json.dumps({
        "event": "leak_processed",
        "tenant_id": hit_data["tenant_id"],
        "source": hit_data["source"],
        "severity": hit_data.get("severity_score", 0),
        "idempotency_key": idempotency_key
    }))
    
    # 4. SOAR Integration & Automated Response (SIEM)
    if hit_data.get("severity_score", 0) >= 90:
        try:
            webhook_url = os.getenv("SOAR_WEBHOOK_URL", "http://soar-mock-url/api/v1/alerts")
            if webhook_url and webhook_url != "http://soar-mock-url/api/v1/alerts":
                import requests
                stix_payload = {"alert_type": "CRITICAL_OSINT_LEAK", "details": hit_data}
                requests.post(webhook_url, json=stix_payload, timeout=3)
                logger.info(f"[SOAR] Fired webhook to SIEM at {webhook_url}")
            else:
                logger.info("[SOAR] Simulated Webhook Fire (CRITICAL SEVERITY DETECTED)")
        except Exception as e:
            logger.error(f"[SOAR] Webhook dispatch failed: {e}")

    # 4. Storage & Indexing with Circuit Breaker
    try:
        asyncio.run(store_and_index(hit_data, raw_content))
    except Exception as e:
        logger.error(json.dumps({
            "event": "storage_failed",
            "error": str(e),
            "idempotency_key": idempotency_key
        }))
        # In un sistema reale, qui potremmo mandare il task in una Dead Letter Queue
        # o fare un retry con Celery
        raise self.retry(exc=e, countdown=60)

    return hit_data["severity_score"]

async def store_and_index(hit_data, raw_content):
    """
    Salvataggio e indicizzazione protetti da Circuit Breaker (#2).
    """
    # 1. MinIO Storage (Raw Content + Screenshot)
    bucket_name = f"tenant-{hit_data['tenant_id']}"
    object_name = f"{hit_data['idempotency_key']}.txt"
    screenshot_name = f"{hit_data['idempotency_key']}.png"
    
    async def upload_to_minio():
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
        
        # Upload Text Content
        content_bytes = raw_content.encode('utf-8')
        minio_client.put_object(
            bucket_name, object_name, 
            io.BytesIO(content_bytes), len(content_bytes),
            content_type="text/plain"
        )

        # Upload Screenshot if available (W)
        screenshot_path = hit_data.get("screenshot_tmp")
        if screenshot_path and os.path.exists(screenshot_path):
            minio_client.fput_object(
                bucket_name, screenshot_name, screenshot_path
            )
            os.remove(screenshot_path) # Cleanup tmp
            return f"minio://{bucket_name}/{object_name}", f"minio://{bucket_name}/{screenshot_name}"

        return f"minio://{bucket_name}/{object_name}", None

    try:
        txt_path, ss_path = await minio_breaker(upload_to_minio)
        hit_data["storage_path"] = txt_path
        hit_data["screenshot_path"] = ss_path
    except Exception as e:
        logger.error(f"[CIRCUIT BREAKER] MinIO storage failed: {e}")
        hit_data["storage_path"] = None
        hit_data["screenshot_path"] = None

    # 2. Elasticsearch Indexing
    es_doc = {
        "tenant_id": hit_data["tenant_id"],
        "source": hit_data["source"],
        "content": raw_content,
        "timestamp": datetime.now().isoformat(),
        "severity": hit_data["severity_score"],
        "metadata": hit_data["metadata_json"],
        "storage_path": hit_data["storage_path"]
    }

    async def index_in_es():
        return await es.index(index="naso-leaks", document=es_doc)

    try:
        await es_breaker(index_in_es)
        logger.info(f"[NASO BATTLE-READY] Leak indexed in ES for tenant {hit_data['tenant_id']}")
    except Exception as e:
        logger.error(f"[CIRCUIT BREAKER] ES indexing skipped/failed: {e}")

    # 3. Correlazione Identità (Command Side)
    # Proteggiamo anche il DB se necessario, ma qui l'idempotenza (#1) gestisce i retry
    async with AsyncSessionLocal() as db:
        await IdentityCorrelationService.correlate_leak(
            db, 
            leak_id=hit_data.get('id'), 
            content=raw_content, 
            tenant_id=hit_data['tenant_id'],
            screenshot_path=hit_data.get('screenshot_path')
        )
    
    logger.info(f"[NASO BATTLE-READY] Identity Correlation complete for tenant {hit_data['tenant_id']}")
