from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.celery_app import celery_app
from shared.database import get_db
from shared.models import Tenant
from shared.schemas import Tenant as TenantSchema
from shared.schemas import TenantCreate
from shared.utils.audit import AuditLogger

from ..deps import check_admin

router = APIRouter()


@router.post("/", response_model=TenantSchema)
async def create_tenant(tenant: TenantCreate, db: AsyncSession = Depends(get_db), current_user=Depends(check_admin)):
    db_tenant = Tenant(name=tenant.name, description=tenant.description)
    db.add(db_tenant)
    await db.flush()

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="CREATE_TENANT",
        resource_type="tenant",
        resource_id=db_tenant.id,
        details={"name": tenant.name},
    )

    await db.commit()
    await db.refresh(db_tenant)
    return db_tenant


@router.get("/", response_model=list[TenantSchema])
async def list_tenants(db: AsyncSession = Depends(get_db), current_user=Depends(check_admin)):
    result = await db.execute(select(Tenant))
    return result.scalars().all()


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(check_admin)):
    """
    Trigger distributed deletion via Saga Pattern (#7).
    Deletes data from ES, MinIO, and DB asynchronously.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    db_tenant = result.scalar_one_or_none()

    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="DELETE_TENANT_TRIGGERED",
        resource_type="tenant",
        resource_id=tenant_id,
    )
    await db.commit()

    # Send task to Celery
    celery_app.send_task("tasks.maintenance.delete_tenant_saga", args=[tenant_id])

    return {"message": f"Deletion saga for tenant {tenant_id} initiated."}
