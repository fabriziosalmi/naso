import jwt
import pytest

from shared.config import settings
from shared.core.security import create_access_token, get_password_hash
from shared.models import Tenant, User


@pytest.fixture
async def test_user(db):
    tenant = Tenant(name="Test TenantCorp")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    user = User(
        email="operator@test.local",
        hashed_password=get_password_hash("securepass123"),
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    response = await client.post("/auth/login", data={"username": "operator@test.local", "password": "securepass123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client, test_user):
    response = await client.post("/auth/login", data={"username": "operator@test.local", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_access_protected_route_without_token(client):
    response = await client.get("/leaks/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_protected_route_with_valid_token(client, test_user):
    # Get token
    login_res = await client.post("/auth/login", data={"username": "operator@test.local", "password": "securepass123"})
    token = login_res.json()["access_token"]

    # Access leaks
    response = await client.get("/leaks/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


# ── JWT claim hardening ───────────────────────────────────────────────────────


def test_minted_token_carries_full_claim_set():
    """create_access_token must emit iss / aud / iat / nbf / exp / jti
    plus whatever the caller passed in. Verifying their *presence* —
    the actual decode-side enforcement is exercised in the rejection
    tests below.
    """
    token = create_access_token({"sub": "x@y.z", "tenant_id": "t1", "role": "admin"})
    payload = jwt.decode(
        token,
        settings.JWT_PUBLIC_KEY,
        algorithms=[settings.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        leeway=settings.JWT_LEEWAY_SECONDS,
    )
    for claim in ("iss", "aud", "iat", "nbf", "exp", "jti", "sub"):
        assert claim in payload, f"missing claim: {claim}"
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE


@pytest.mark.asyncio
async def test_token_with_wrong_audience_rejected(client, test_user):
    """A token signed with this server's key but for a different audience
    (e.g. a sibling MCP service that happens to share the keypair) must
    be refused on the API."""
    bogus = jwt.encode(
        {
            "sub": test_user.email,
            "tenant_id": test_user.tenant_id,
            "role": test_user.role,
            "iss": settings.JWT_ISSUER,
            "aud": "some-other-service",
            "jti": "bogus-jti",
        },
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = await client.get("/leaks/", headers={"Authorization": f"Bearer {bogus}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_with_wrong_issuer_rejected(client, test_user):
    bogus = jwt.encode(
        {
            "sub": test_user.email,
            "tenant_id": test_user.tenant_id,
            "role": test_user.role,
            "iss": "spoofed-issuer",
            "aud": settings.JWT_AUDIENCE,
            "jti": "bogus-jti-2",
        },
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = await client.get("/leaks/", headers={"Authorization": f"Bearer {bogus}"})
    assert response.status_code == 401
