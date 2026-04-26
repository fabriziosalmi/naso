import pytest

from shared.core.security import get_password_hash
from shared.models import LeakHit, Tenant, User

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def tenant(db):
    t = Tenant(name="AcmeCorp Security")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def admin_user(db, tenant):
    u = User(
        email="admin@acme.local",
        hashed_password=get_password_hash("Admin$ecure99"),
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def analyst_user(db, tenant):
    u = User(
        email="analyst@acme.local",
        hashed_password=get_password_hash("Analyst$ecure99"),
        tenant_id=tenant.id,
        role="analyst",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def auth_headers(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.local", "password": "Admin$ecure99"},
    )
    token = res.json()["access_token"]
    # Include the CSRF token: the login response sets the cookie, and the
    # test client persists it across requests, so any subsequent mutating
    # call hits the CSRFMiddleware. Bearer-only callers wouldn't need
    # this — but the test client's cookie jar already carries the auth
    # cookie, so the middleware treats it as a cookie-auth request.
    csrf = res.cookies["naso_csrf"]
    return {"Authorization": f"Bearer {token}", "X-Naso-CSRF": csrf}


@pytest.fixture
async def analyst_headers(client, analyst_user):
    res = await client.post(
        "/auth/login",
        data={"username": "analyst@acme.local", "password": "Analyst$ecure99"},
    )
    token = res.json()["access_token"]
    csrf = res.cookies["naso_csrf"]
    return {"Authorization": f"Bearer {token}", "X-Naso-CSRF": csrf}


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
    """G-09: /system/status non deve esporre dettagli interni di errore."""
    response = await client.get("/system/status")
    assert "error" not in response.json()


@pytest.mark.asyncio
async def test_trusted_host_rejects_unknown_host_header(client):
    """TrustedHostMiddleware drops a request whose Host header is not in
    settings.ALLOWED_HOSTS. The dev default permits localhost / docker /
    the pytest httpx hostnames; an arbitrary value like "evil.example.com"
    must hit a 400 from Starlette before any route runs.
    """
    response = await client.get("/system/status", headers={"host": "evil.example.com"})
    assert response.status_code == 400


# ── Auth ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_protected_route(client):
    response = await client.get("/leaks/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_token_and_cookie(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.local", "password": "Admin$ecure99"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["token_type"] == "bearer"
    # Cookie httpOnly deve essere impostato (C-05)
    assert "naso_access_token" in res.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    res = await client.post(
        "/auth/login",
        data={"username": "admin@acme.local", "password": "wrongpassword"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    res = await client.post(
        "/auth/login",
        data={"username": "ghost@nowhere.local", "password": "whatever"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, admin_user):
    login = await client.post(
        "/auth/login",
        data={"username": "admin@acme.local", "password": "Admin$ecure99"},
    )
    token = login.json()["access_token"]
    csrf = login.cookies["naso_csrf"]
    res = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}", "X-Naso-CSRF": csrf},
    )
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
    """Multi-tenancy: un analista non deve vedere i leak di un altro tenant."""
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
    """Cambiare solo il full_name non richiede password."""
    res = await client.put(
        "/users/me",
        json={"full_name": "New Name"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_email_requires_current_password(client, auth_headers):
    """C-12: cambiare email senza current_password deve essere rifiutato."""
    res = await client.put(
        "/users/me",
        json={"email": "new@acme.local"},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_email_wrong_password_rejected(client, auth_headers):
    res = await client.put(
        "/users/me",
        json={"email": "new@acme.local", "current_password": "wrongpass"},
        headers=auth_headers,
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_email_correct_password(client, auth_headers):
    res = await client.put(
        "/users/me",
        json={"email": "updated@acme.local", "current_password": "Admin$ecure99"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["email"] == "updated@acme.local"


# ── Keywords ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_keyword(client, auth_headers, tenant, admin_user):
    res = await client.post(
        "/keywords/",
        json={"value": "acmecorp_breach", "tenant_id": tenant.id},
        headers=auth_headers,
    )
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_analyst_cannot_access_admin_routes(client, analyst_headers):
    """RBAC: un analyst non deve accedere alle route /tenants/ (solo admin)."""
    res = await client.get("/tenants/", headers=analyst_headers)
    assert res.status_code == 403


# ── Shodan IP validation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shodan_rejects_invalid_ip(client, auth_headers):
    """G-03: il parametro ip deve essere validato."""
    res = await client.get("/leaks/recon/shodan?ip=not_an_ip", headers=auth_headers)
    assert res.status_code == 400
    assert "Invalid IP address" in res.json()["detail"]


# ── Pydantic input validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_leak_status_rejects_unknown_value(client, auth_headers):
    """LeakStatus is a closed Literal — values outside the allowed set hit
    a FastAPI 422 during query-param validation, before the route body
    runs. We don't need an actual row.
    """
    res = await client.patch("/leaks/whatever/status?status=bogus", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_leaks_rejects_unknown_status_filter(client, auth_headers):
    res = await client.get("/leaks/?status=bogus", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_ingest_webhook_rejects_oversized_content_length(client, auth_headers):
    """Client lies about a 5MB body — middleware short-circuits with 413."""
    big = 5 * 1024 * 1024
    res = await client.post(
        "/leaks/ingest/webhook",
        content=b"{}",
        headers={**auth_headers, "Content-Length": str(big)},
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_ingest_webhook_rejects_invalid_payload_shape(client, auth_headers):
    """Body parses as JSON but doesn't match WebhookPayload — 422 from pydantic."""
    res = await client.post(
        "/leaks/ingest/webhook",
        json={"missing_required_source_and_content": True},
        headers=auth_headers,
    )
    assert res.status_code == 422
