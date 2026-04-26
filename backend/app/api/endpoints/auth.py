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

from ...csrf import clear_csrf_cookie, issue_csrf_token, set_csrf_cookie
from ...limiter import limiter
from ..deps import oauth2_scheme

router = APIRouter()

_COOKIE_NAME = "naso_access_token"
_COOKIE_SAMESITE = "lax"  # 'strict' romperebbe il proxy Vite in sviluppo


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

    # Imposta il token come cookie httpOnly — il JS non può leggerlo (protezione XSS)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=os.getenv("NASO_COOKIE_SECURE", "false").lower() == "true",
        max_age=int(access_token_expires.total_seconds()),
        path="/",
    )

    # Issue a fresh CSRF token bound to the same lifetime. The SPA reads
    # this cookie via document.cookie and echoes it on every mutating
    # request as the X-Naso-CSRF header; CSRFMiddleware enforces the match.
    set_csrf_cookie(response, issue_csrf_token(), max_age=int(access_token_expires.total_seconds()))

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request, response: Response, token: str = Depends(oauth2_scheme)):
    # Cancella il cookie httpOnly
    response.delete_cookie(key=_COOKIE_NAME, httponly=True, samesite=_COOKIE_SAMESITE, path="/")
    # And the companion CSRF cookie — leaving it would let a stale token
    # match itself if the same cookie name got re-used by another tab.
    clear_csrf_cookie(response)

    try:
        # Verifica la firma prima di aggiungere alla blacklist. Same iss/aud
        # checks as deps.get_current_user — a token that doesn't validate
        # cleanly here can't have come from us, so we don't blacklist it.
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
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
        # Cookie già cancellato — il logout è comunque effettivo
        return {"msg": "Logged out"}
