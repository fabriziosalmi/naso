import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from ..config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # iss/aud scope the token to this deployment; nbf closes the window in
    # which a token is signed but not yet nominally valid. decode_access_token
    # verifies all three, so they are not decoration.
    to_encode.update(
        {
            "exp": expire,
            "jti": jti,
            "iat": now,
            "nbf": now,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
    )

    encoded_jwt = jwt.encode(to_encode, settings.JWT_PRIVATE_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Verify and decode an access token.

    The single decode path for the whole codebase. Call sites used to pass
    their own argument set to ``jwt.decode``, which is how you end up with one
    endpoint checking the audience and another not. Raises ``jwt.PyJWTError``
    (or a subclass) on anything invalid — callers translate that into a 401.
    """
    return jwt.decode(
        token,
        settings.JWT_PUBLIC_KEY,
        algorithms=[settings.ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        leeway=settings.JWT_LEEWAY_SECONDS,
        options={"require": ["exp", "iat", "nbf", "iss", "aud", "jti", "sub"]},
    )
