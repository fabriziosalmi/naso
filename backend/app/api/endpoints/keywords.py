from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.database import get_db
from shared.models import Keyword
from shared.schemas import Keyword as KeywordSchema
from shared.schemas import KeywordCreate

from ..deps import get_current_user

router = APIRouter()


@router.post("/", response_model=KeywordSchema)
async def create_keyword(
    keyword: KeywordCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    # Check that the user belongs to the tenant, or is an admin
    if current_user.role != "admin" and current_user.tenant_id != keyword.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this tenant")

    db_keyword = Keyword(value=keyword.value, type=keyword.type, tenant_id=keyword.tenant_id)
    db.add(db_keyword)
    await db.commit()
    await db.refresh(db_keyword)
    return db_keyword


@router.get("/", response_model=list[KeywordSchema])
async def list_keywords(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    query = select(Keyword)
    if current_user.role != "admin":
        query = query.where(Keyword.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    return result.scalars().all()
