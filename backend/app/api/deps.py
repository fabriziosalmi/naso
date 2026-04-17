import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.config import settings
from shared.core.jwt_manager import jwt_blacklist
from shared.database import get_db
from shared.models import User
from shared.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=[settings.ALGORITHM])
        jti: str = payload.get("jti")
        email: str = payload.get("sub")

        if email is None or jti is None:
            raise credentials_exception

        if await jwt_blacklist.is_blacklisted(jti):
            raise credentials_exception

        token_data = TokenData(email=email, tenant_id=payload.get("tenant_id"), role=payload.get("role"))
    except jwt.PyJWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == token_data.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def check_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user
