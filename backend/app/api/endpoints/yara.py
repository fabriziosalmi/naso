
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.database import get_db
from shared.models import YaraRule
from shared.schemas import YaraRule as YaraRuleSchema
from shared.schemas import YaraRuleCreate
from shared.utils.audit import AuditLogger

from ..deps import get_current_user

router = APIRouter()


@router.post("/", response_model=YaraRuleSchema)
async def create_yara_rule(
    rule: YaraRuleCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Crea una nuova regola YARA. Gli admin possono creare regole globali.
    """
    if not current_user.role == "admin" and rule.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to create rule for this tenant")

    db_rule = YaraRule(
        name=rule.name,
        content=rule.content,
        tenant_id=rule.tenant_id if current_user.role == "admin" else current_user.tenant_id,
        is_active=rule.is_active,
    )
    db.add(db_rule)
    await db.flush()

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="CREATE_YARA_RULE",
        resource_type="yara_rule",
        resource_id=db_rule.id,
        details={"name": rule.name},
    )

    await db.commit()
    await db.refresh(db_rule)
    return db_rule


@router.get("/", response_model=list[YaraRuleSchema])
async def list_yara_rules(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Lista le regole YARA attive (globali + specifiche del tenant).
    """
    query = select(YaraRule).where(YaraRule.is_active)
    if current_user.role != "admin":
        query = query.where((YaraRule.tenant_id == current_user.tenant_id) | (YaraRule.tenant_id.is_(None)))

    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{rule_id}")
async def delete_yara_rule(rule_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(YaraRule).where(YaraRule.id == rule_id))
    db_rule = result.scalar_one_or_none()

    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if current_user.role != "admin" and db_rule.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="DELETE_YARA_RULE",
        resource_type="yara_rule",
        resource_id=rule_id,
        details={"name": db_rule.name},
    )

    await db.delete(db_rule)
    await db.commit()
    return {"status": "success"}
