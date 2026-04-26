from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.core.exceptions import ResourceNotFoundError
from shared.core.security import verify_password
from shared.database import get_db
from shared.models import User
from shared.schemas import User as UserSchema
from shared.schemas import UserUpdate
from shared.utils.audit import AuditLogger

from ..deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def read_operator_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated operator's profile.

    Used by the SPA to restore session state on a hard refresh: the
    auth cookie is httpOnly, so the JS layer cannot inspect it directly
    and instead pings this endpoint. A 200 confirms the cookie still
    decodes; a 401 makes the SPA fall back to the login screen.
    """
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_operator_profile(
    user_update: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Updates the current operator's profile (e.g., email change).
    Changing the email requires the current password to prevent account takeover.
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise ResourceNotFoundError("Operator not found")

    old_email = user.email

    if user_update.email and user_update.email != user.email:
        # Verifica password obbligatoria per il cambio email (OWASP A07)
        if not user_update.current_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="current_password is required to change your email address",
            )
        if not verify_password(user_update.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        user.email = user_update.email

    if user_update.full_name:
        user.full_name = user_update.full_name

    await AuditLogger.log(
        db,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="UPDATE_PROFILE",
        resource_type="user",
        resource_id=user.id,
        details={"old_email": old_email, "new_email": user.email},
    )

    await db.commit()
    await db.refresh(user)

    return user
