import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from ..config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Mint a NASO access token.

    Adds the full set of standard JWT claims:
      * iss / aud — pin the token to this issuer + audience pair so a
        token signed for a sibling service can't be replayed at the API.
      * iat / nbf — both set to "now"; nbf prevents a clock-skew window
        where a token would be valid before its issuance time.
      * exp — explicit lifetime (settings.ACCESS_TOKEN_EXPIRE_MINUTES
        when no caller override).
      * jti — unique identifier so the blacklist can revoke a single
        token without taking down the whole signing key.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode.update(
        {
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }
    )

    encoded_jwt = jwt.encode(to_encode, settings.JWT_PRIVATE_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
