import os
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.config import settings
from shared.core.jwt_manager import jwt_blacklist
from shared.core.security import create_access_token, verify_password
from shared.database import get_db
from shared.models import User
from shared.schemas import Token

from ...limiter import limiter
from ..deps import oauth2_scheme

router = APIRouter()

_COOKIE_NAME = "naso_access_token"
_COOKIE_SAMESITE = "lax"  # 'strict' would break the Vite dev proxy


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login_for_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):

    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "tenant_id": user.tenant_id, "role": user.role}, expires_delta=access_token_expires
    )

    # Set the token as an httpOnly cookie — JS cannot read it (XSS protection)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=os.getenv("NASO_COOKIE_SECURE", "false").lower() == "true",
        max_age=int(access_token_expires.total_seconds()),
        path="/",
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request, response: Response, token: str = Depends(oauth2_scheme)):
    # Clear the httpOnly cookie
    response.delete_cookie(key=_COOKIE_NAME, httponly=True, samesite=_COOKIE_SAMESITE, path="/")

    try:
        # Verify the signature before blacklisting (C-01 fix retained)
        payload = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).timestamp()
            ttl = int(exp - now)
            if ttl > 0:
                await jwt_blacklist.blacklist_token(jti, ttl)
        return {"msg": "Successfully logged out"}
    except jwt.PyJWTError:
        # Cookie already cleared — the logout is effective either way
        return {"msg": "Logged out"}
