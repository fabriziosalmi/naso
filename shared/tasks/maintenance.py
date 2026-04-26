# ruff: noqa: E402
import asyncio
import json
import logging
import os

from elasticsearch import AsyncElasticsearch
from minio import Minio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.celery_app import celery_app
from shared.config import settings
from shared.models import AuditLog, Identity, Keyword, LeakHit, Tenant, User, identity_leaks

logger = logging.getLogger("naso-maintenance")

# Database Setup
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://naso_admin:rigorous_admin_password_2026@db:5432/naso_db")
engine = create_async_engine(DB_URL)

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
    es = AsyncElasticsearch(
        f"https://elastic:{settings.ES_PASSWORD}@{settings.ES_HOST}:{settings.ES_PORT}",
        verify_certs=settings.ES_VERIFY_CERTS,
    )
    try:
        # Delete by query for the specific tenant
        query = {"query": {"term": {"tenant_id": tenant_id}}}
        response = await es.delete_by_query(index="naso-leaks", body=query, wait_for_completion=True)
        logger.info(f"[SAGA] ES deletion for tenant {tenant_id}: {response}")
    finally:
        await es.close()


async def delete_from_minio(tenant_id: str):
    minio_client = Minio(
        settings.MINIO_ENDPOINT,
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
