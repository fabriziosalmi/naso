"""Tests for the registered claims on the access token.

Before this, ``jwt.decode`` was called with nothing but the key and the
algorithm, which means any token signed by that key was accepted: one minted
by a sibling service sharing the key pair, or one minted for a different NASO
deployment. These tests pin the four properties that fixes:

  * the minted token actually carries iss/aud/nbf/jti/iat/exp;
  * a wrong audience is rejected;
  * a wrong issuer is rejected;
  * a token that is not yet valid (nbf in the future) is rejected, and the
    configured leeway is what decides the boundary.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from shared.config import settings
from shared.core.security import create_access_token, decode_access_token


def _mint(**overrides) -> str:
    """Sign a token directly, bypassing create_access_token's claim set."""
    now = datetime.now(UTC)
    payload = {
        "sub": "claims@naso.example.com",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=settings.ALGORITHM)


def test_minted_token_carries_the_registered_claims():
    payload = decode_access_token(create_access_token({"sub": "claims@naso.example.com"}))
    for claim in ("exp", "iat", "nbf", "iss", "aud", "jti", "sub"):
        assert claim in payload, f"missing claim: {claim}"
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE


def test_round_trip_accepts_a_well_formed_token():
    assert decode_access_token(_mint())["sub"] == "claims@naso.example.com"


def test_wrong_audience_is_rejected():
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(_mint(aud="some-other-api"))


def test_wrong_issuer_is_rejected():
    with pytest.raises(jwt.InvalidIssuerError):
        decode_access_token(_mint(iss="not-naso"))


def test_missing_claim_is_rejected():
    # A correctly signed token that simply omits the audience must not slip
    # through — `require` is what makes iss/aud non-optional rather than
    # "checked only if present".
    token = jwt.encode(
        {"sub": "x@naso.example.com", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


def test_not_yet_valid_token_is_rejected_beyond_the_leeway():
    future = datetime.now(UTC) + timedelta(seconds=settings.JWT_LEEWAY_SECONDS + 60)
    with pytest.raises(jwt.ImmatureSignatureError):
        decode_access_token(_mint(nbf=future, iat=future))


def test_small_clock_skew_is_tolerated():
    # A token from a host a few seconds ahead must still work; that is the
    # whole point of the leeway, and without it a fleet with imperfect NTP
    # produces intermittent 401s that look like an auth bug.
    skewed = datetime.now(UTC) + timedelta(seconds=settings.JWT_LEEWAY_SECONDS - 5)
    assert decode_access_token(_mint(nbf=skewed, iat=skewed))["sub"] == "claims@naso.example.com"


def test_expired_token_is_rejected():
    past = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(_mint(iat=past, nbf=past, exp=past + timedelta(minutes=5)))
