"""Tests for the double-submit-cookie CSRF middleware.

The matrix we care about:

  * Safe method (GET) — middleware never runs the check.
  * Bearer-only POST — no auth cookie, so no browser-CSRF threat;
    middleware skips and the request is decided by auth alone.
  * Cookie-auth POST without the X-Naso-CSRF header — 403.
  * Cookie-auth POST with a mismatched header — 403.
  * Cookie-auth POST with the matching header — 200.
  * /auth/login itself is unconditionally exempt; without that the SPA
    couldn't bootstrap a session.
"""

import pytest
import pytest_asyncio

from shared.core.security import get_password_hash
from shared.models import Tenant, User


@pytest_asyncio.fixture
async def admin_user(db):
    t = Tenant(name="csrf-tenant")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    u = User(
        email="csrf-admin@naso.example.com",
        hashed_password=get_password_hash("Csrf$ecure99"),
        tenant_id=t.id,
        role="admin",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _login(client, email="csrf-admin@naso.example.com", password="Csrf$ecure99"):
    res = await client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return res


@pytest.mark.asyncio
async def test_login_sets_both_cookies(client, admin_user):
    res = await _login(client)
    # httpOnly auth cookie + non-httpOnly CSRF cookie are both issued.
    assert "naso_access_token" in res.cookies
    assert "naso_csrf" in res.cookies
    assert res.cookies["naso_csrf"]  # non-empty


@pytest.mark.asyncio
async def test_get_requests_skip_csrf(client, admin_user):
    await _login(client)
    # /system/audit is GET → middleware short-circuits regardless of header.
    res = await client.get("/system/audit")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_cookie_auth_post_without_header_is_blocked(client, admin_user):
    await _login(client)
    res = await client.post("/leaks/ack-all", json={"min_severity": 80})
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]


@pytest.mark.asyncio
async def test_cookie_auth_post_with_mismatched_header_is_blocked(client, admin_user):
    await _login(client)
    res = await client.post(
        "/leaks/ack-all",
        json={"min_severity": 80},
        headers={"X-Naso-CSRF": "this-is-not-the-real-token"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cookie_auth_post_with_matching_header_passes(client, admin_user):
    login = await _login(client)
    csrf_token = login.cookies["naso_csrf"]
    res = await client.post(
        "/leaks/ack-all",
        json={"min_severity": 80},
        headers={"X-Naso-CSRF": csrf_token},
    )
    # The endpoint itself returns 200 — middleware let the request through.
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_bearer_only_post_skips_csrf(client, admin_user):
    """Server-to-server callers (webhooks, MCP) don't carry the cookie.
    The middleware must let them through; auth is the right control there.
    """
    login = await client.post(
        "/auth/login",
        data={"username": "csrf-admin@naso.example.com", "password": "Csrf$ecure99"},
    )
    bearer = login.json()["access_token"]
    # Drop the cookies the test client kept from /auth/login so this
    # request looks like a pure Bearer call.
    client.cookies.clear()
    res = await client.post(
        "/leaks/ack-all",
        json={"min_severity": 80},
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_logout_clears_csrf_cookie(client, admin_user):
    login = await _login(client)
    csrf_token = login.cookies["naso_csrf"]
    res = await client.post(
        "/auth/logout",
        headers={"X-Naso-CSRF": csrf_token},
    )
    assert res.status_code == 200
    # Starlette signals deletion via Set-Cookie with Max-Age=0; httpx
    # exposes the deletion as the cookie no longer being in the jar.
    assert "naso_csrf" not in client.cookies
