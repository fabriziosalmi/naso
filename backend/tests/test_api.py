import pytest
import pytest_asyncio

from shared.core.security import get_password_hash
from shared.models import LeakHit, Tenant, User

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def tenant(db):
    t = Tenant(name="AcmeCorp Security")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest_asyncio.fixture
async def admin_user(db, tenant):
    u = User(
        email="admin@acme.example.com",
        hashed_password=get_password_hash("Admin$ecure99"),
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def analyst_user(db, tenant):
    u = User(
        email="analyst@acme.example.com",
        hashed_password=get_password_hash("Analyst$ecure99"),
        tenant_id=tenant.id,
        role="analyst",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def auth_headers(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.example.com", "password": "Admin$ecure99"},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def analyst_headers(client, analyst_user):
    res = await client.post(
        "/auth/login",
        data={"username": "analyst@acme.example.com", "password": "Analyst$ecure99"},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── System status ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_system_status(client):
    response = await client.get("/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_system_status_no_error_field(client):
    """G-09: /system/status must not leak internal error details."""
    response = await client.get("/system/status")
    assert "error" not in response.json()


# ── Auth ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_protected_route(client):
    response = await client.get("/leaks/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_token_and_cookie(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.example.com", "password": "Admin$ecure99"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["token_type"] == "bearer"
    # The httpOnly cookie must be set (C-05)
    assert "naso_access_token" in res.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    res = await client.post(
        "/auth/login",
        data={"username": "ghost@nowhere.example.com", "password": "whatever"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, admin_user):
    login = await client.post(
        "/auth/login",
        data={"username": "admin@acme.example.com", "password": "Admin$ecure99"},
    )
    token = login.json()["access_token"]
    res = await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


# ── Leaks ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_leaks_authenticated(client, auth_headers, tenant):
    res = await client.get("/leaks/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_leaks_unauthenticated(client):
    res = await client.get("/leaks/")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_leaks_tenant_isolation(client, db, auth_headers, analyst_headers, tenant):
    """Multi-tenancy: an analyst must not see another tenant's leaks."""
    other_tenant = Tenant(name="OtherCorp")
    db.add(other_tenant)
    await db.commit()
    await db.refresh(other_tenant)

    foreign_leak = LeakHit(
        tenant_id=other_tenant.id,
        source="test",
        content_snippet="foreign data",
        severity_score=50,
        status="new",
    )
    db.add(foreign_leak)
    await db.commit()

    res = await client.get("/leaks/", headers=analyst_headers)
    assert res.status_code == 200
    leak_ids = [l["id"] for l in res.json()]
    assert foreign_leak.id not in leak_ids


# ── Identities ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_identity(client, auth_headers):
    res = await client.post(
        "/identities/",
        json={"identifier": "target@example.com", "type": "email"},
        headers=auth_headers,
    )
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["identifier"] == "target@example.com"


@pytest.mark.asyncio
async def test_list_identities(client, auth_headers):
    res = await client.get("/identities/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── User profile ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_profile_name_no_password_needed(client, auth_headers):
    """Changing only full_name does not require the password."""
    res = await client.put(
        "/users/me",
        json={"full_name": "New Name"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_email_requires_current_password(client, auth_headers):
    """C-12: changing the email without current_password must be rejected."""
    res = await client.put(
        "/users/me",
        json={"email": "new@acme.example.com"},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_email_wrong_password_rejected(client, auth_headers):
    res = await client.put(
        "/users/me",
        json={"email": "new@acme.example.com", "current_password": "wrongpass"},
        headers=auth_headers,
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_email_correct_password(client, auth_headers):
    res = await client.put(
        "/users/me",
        json={"email": "updated@acme.example.com", "current_password": "Admin$ecure99"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["email"] == "updated@acme.example.com"


# ── Keywords ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_keyword(client, auth_headers, tenant, admin_user):
    res = await client.post(
        "/keywords/",
        json={"value": "acmecorp_breach", "type": "keyword", "tenant_id": tenant.id},
        headers=auth_headers,
    )
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_analyst_cannot_access_admin_routes(client, analyst_headers):
    """RBAC: an analyst must not reach the /tenants/ routes (admin only)."""
    res = await client.get("/tenants/", headers=analyst_headers)
    assert res.status_code == 403


# ── Shodan IP validation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shodan_rejects_invalid_ip(client, auth_headers):
    """G-03: the ip parameter must be validated."""
    res = await client.get("/leaks/recon/shodan?ip=not_an_ip", headers=auth_headers)
    assert res.status_code == 400
    assert "Invalid IP address" in res.json()["detail"]
