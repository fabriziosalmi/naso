from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from shared.database import get_db
from shared.models import User
from shared.schemas import User as UserSchema, UserUpdate
from .deps import get_current_user
from shared.utils.audit import AuditLogger
from shared.core.exceptions import ResourceNotFoundError

router = APIRouter()

@router.put("/me", response_model=UserSchema)
async def update_operator_profile(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the current operator's profile (e.g., email change).
    Triggers an audit log.
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise ResourceNotFoundError("Operator not found")
        
    old_email = user.email
    
    if user_update.email:
        user.email = user_update.email
    if user_update.full_name:
        user.full_name = user_update.full_name
        
    # Log the action in the audit trail
    await AuditLogger.log(
        db, 
        user_id=user.id, 
        tenant_id=user.tenant_id,
        action="UPDATE_PROFILE", 
        resource_type="user", 
        resource_id=user.id,
        details={"old_email": old_email, "new_email": user.email}
    )
    
    await db.commit()
    await db.refresh(user)
    
    return user
