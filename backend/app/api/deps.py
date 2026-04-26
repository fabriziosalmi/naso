import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.config import settings
from shared.core.jwt_manager import jwt_blacklist
from shared.database import get_db
from shared.models import User
from shared.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

_COOKIE_NAME = "naso_access_token"


def _extract_token(request: Request, bearer_token: str | None) -> str | None:
    """Prova prima il cookie httpOnly, poi l'header Authorization Bearer."""
    cookie_token = request.cookies.get(_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return bearer_token


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    bearer_token: str | None = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(request, bearer_token)
    if not token:
        raise credentials_exception

    try:
        # Verify standard claims explicitly. ``algorithms`` is a list of
        # exactly one entry to prevent the alg-confusion family of
        # attacks; iss/aud must match the values minted by
        # create_access_token; leeway tolerates small clock skew.
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
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
