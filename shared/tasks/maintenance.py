# ruff: noqa: E402
import asyncio
import json
import logging

from minio import Minio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from shared.celery_app import celery_app
from shared.config import settings
from shared.core.es_client import make_es_client
from shared.models import AuditLog, Identity, Keyword, LeakHit, Tenant, User, identity_leaks

# pipeline.py used to re-export these as module constants and now reads them
# off `settings` directly. Importing the old names killed the worker at
# startup: celery imports every module in its `include` list, so the
# ImportError took down the whole worker, not just this task.

logger = logging.getLogger("naso-maintenance")

# Database Setup
# No credential-bearing fallback: if DATABASE_URL is unset this should fail
# loudly rather than quietly try a password baked into the source.
DB_URL = settings.DATABASE_URL
# NullPool for exactly the reason pipeline.py uses it, and this is the copy that
# was missed. delete_tenant_saga runs each step under its own asyncio.run(),
# which opens a fresh event loop and closes it. With the default pool the asyncpg
# connection is returned to a module-level pool still bound to that now-closed
# loop; the NEXT tenant deletion in the same long-lived prefork worker checks it
# back out and every query fails with "Event loop is closed", through all five
# retries, until the process restarts. So the first erasure per worker succeeded
# and every one after it silently failed — a GDPR right-to-erasure operation.
# NullPool opens and closes a connection per use, so nothing is retained across
# loops.
engine = create_async_engine(
    DB_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args={"prepared_statement_cache_size": 0, "statement_cache_size": 0},
)

from shared.utils.worker_tracing import setup_worker_tracing

setup_worker_tracing(engine)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, name="tasks.maintenance.delete_tenant_saga")
def delete_tenant_saga(self, tenant_id: str):
    """
    Saga Pattern Orchestrator (#7) for Distributed Tenant Deletion.
    Steps:
    1. Delete from Elasticsearch
    2. Delete from MinIO
    3. Delete from Relational DB
    """
    try:
        # 1. Elasticsearch Deletion
        asyncio.run(delete_from_es(tenant_id))

        # 2. MinIO Deletion
        asyncio.run(delete_from_minio(tenant_id))

        # 3. Database Deletion (Final Step / Source of Truth)
        asyncio.run(delete_from_db(tenant_id))

        logger.info(json.dumps({"event": "tenant_deleted_saga_complete", "tenant_id": tenant_id, "status": "success"}))

    except Exception as e:
        logger.error(json.dumps({"event": "tenant_deleted_saga_failed", "tenant_id": tenant_id, "error": str(e)}))
        # Retry logic: deletion is idempotent, so we can just retry the whole saga
        raise self.retry(exc=e, countdown=300, max_retries=5)


async def delete_from_es(tenant_id: str):
    es = make_es_client()
    try:
        # Delete by query for the specific tenant
        query = {"query": {"term": {"tenant_id": tenant_id}}}
        response = await es.delete_by_query(index="naso-leaks", body=query, wait_for_completion=True)
        logger.info(f"[SAGA] ES deletion for tenant {tenant_id}: {response}")
    finally:
        await es.close()


async def delete_from_minio(tenant_id: str):
    minio_client = Minio(
        settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    bucket_name = f"tenant-{tenant_id}"

    if minio_client.bucket_exists(bucket_name):
        # MinIO requires bucket to be empty before deletion
        objects_to_delete = minio_client.list_objects(bucket_name, recursive=True)
        for obj in objects_to_delete:
            minio_client.remove_object(bucket_name, obj.object_name)

        minio_client.remove_bucket(bucket_name)
        logger.info(f"[SAGA] MinIO bucket {bucket_name} deleted")


async def delete_from_db(tenant_id: str):
    async with AsyncSessionLocal() as session, session.begin():
        # Order matters for foreign keys if not using CASCADE
        # 1. Association table (Identity-Leak)
        # We need to find leaks of the tenant first
        # Or we can do a more complex delete if supported by asyncpg/sqlalchemy

        # Since we want to be "Merciless", we perform targeted deletions

        # Subquery to get all leak IDs for this tenant
        from sqlalchemy import select

        leak_ids_stmt = select(LeakHit.id).where(LeakHit.tenant_id == tenant_id)
        leak_ids_result = await session.execute(leak_ids_stmt)
        leak_ids = [r[0] for r in leak_ids_result.all()]

        if leak_ids:
            await session.execute(delete(identity_leaks).where(identity_leaks.c.leak_id.in_(leak_ids)))

        # 2. Other tables
        await session.execute(delete(Identity).where(Identity.tenant_id == tenant_id))
        await session.execute(delete(LeakHit).where(LeakHit.tenant_id == tenant_id))
        await session.execute(delete(Keyword).where(Keyword.tenant_id == tenant_id))
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))

        # Deletion of tenant-specific webhooks and YARA rules
        from shared.models import Webhook, YaraRule

        await session.execute(delete(Webhook).where(Webhook.tenant_id == tenant_id))
        await session.execute(delete(YaraRule).where(YaraRule.tenant_id == tenant_id))

        await session.execute(delete(User).where(User.tenant_id == tenant_id))

        # 3. Finally the Tenant itself
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))

        await session.commit()
        logger.info(f"[SAGA] Database records for tenant {tenant_id} deleted")
