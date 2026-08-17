"""The four gaps PR #9 closed in April and the August rewrite left open.

#9 ("v1.2.0 — hardening release") has been open since 26 April and never
merged; #21 and #38 rebuilt most of its content on fresh branches. These are the
items that did not make the crossing, each verified against `main` before being
fixed:

  * `GET /users/me` — the SPA calls it on every load and it answered `405`, so a
    page refresh returned the operator to the login screen with a valid session
    cookie in the jar;
  * CSV export wrote attacker-supplied strings unescaped, so a leak `source` of
    `=cmd|…` is a formula when the analyst opens the export (CWE-1236);
  * `POST /leaks/ingest/webhook` — the cheapest path into the Celery pipeline —
    had no rate limit while `/auth/login` has had one since the OWASP pass;
  * `GET /system/audit/verify?tenant_id=` was documented for admins, never
    declared as a parameter, and silently answered about the caller's own
    tenant instead.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from shared.core.security import get_password_hash
from shared.models import AuditLog, LeakHit, Tenant, User


async def _operator(db, role="analyst"):
    tenant = Tenant(id=str(uuid.uuid4()), name=f"acme-{uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    user = User(
        id=str(uuid.uuid4()),
        email=f"op-{uuid.uuid4().hex[:6]}@naso.example.com",
        hashed_password=get_password_hash("Str0ng&Pass!"),
        tenant_id=tenant.id,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return tenant, user


async def _login(client, email, password="Str0ng&Pass!"):
    r = await client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(client, token):
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def operator(db):
    return await _operator(db)


# ── GET /users/me ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_users_me_returns_the_caller(client, db, operator):
    _, user = operator
    token = await _login(client, user.email)

    r = await client.get("/users/me", headers=_bearer(client, token))

    # 405 here is the regression: only PUT /me existed, so the SPA's session
    # probe could never succeed and every reload logged the operator out.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == user.email
    assert body["id"] == user.id
    # Whatever else the schema grows, the password must never be in it.
    assert "hashed_password" not in body
    assert "password" not in body


@pytest.mark.asyncio
async def test_get_users_me_requires_authentication(client):
    assert (await client.get("/users/me")).status_code in (401, 403)


# ── CSV formula injection ───────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["=cmd|' /c calc'!A1", "+1+1", "-2+3", "@SUM(A1)", "\t=1+1", "\r=1+1"])
async def test_csv_export_neutralises_formulas(client, db, operator, payload):
    """Every prefix a spreadsheet reads as a formula must come back quoted."""
    tenant, user = operator
    db.add(
        LeakHit(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            source=payload,
            severity_score=91,
            status="new",
            content_snippet="synthetic",
            discovered_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    token = await _login(client, user.email)
    r = await client.get("/leaks/export/data?format=csv", headers=_bearer(client, token))
    assert r.status_code == 200, r.text

    # The cell may be quoted by the csv writer; what matters is that the value
    # inside it no longer starts with the formula trigger.
    body = r.text
    assert payload not in body.replace("'" + payload, ""), "the raw formula reached the export unescaped"
    assert "'" + payload in body or "'" + payload.replace("\r", "") in body


@pytest.mark.asyncio
async def test_csv_export_leaves_ordinary_values_alone(client, db, operator):
    tenant, user = operator
    db.add(
        LeakHit(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            source="github",
            severity_score=42,
            status="reviewing",
            content_snippet="synthetic",
            discovered_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    token = await _login(client, user.email)
    r = await client.get("/leaks/export/data?format=csv", headers=_bearer(client, token))
    assert r.status_code == 200
    assert "github" in r.text
    assert "'github" not in r.text


# ── /system/audit paging and cross-tenant verification ──────────────────────


@pytest.mark.asyncio
async def test_audit_log_is_pageable(client, db, operator):
    tenant, user = operator
    for i in range(5):
        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"ACTION_{i}",
                resource_type="leak",
                resource_id=str(i),
                timestamp=datetime.now(timezone.utc),
            )
        )
    await db.commit()
    token = await _login(client, user.email)
    headers = _bearer(client, token)

    first = await client.get("/system/audit?limit=2", headers=headers)
    assert first.status_code == 200, first.text
    assert len(first.json()) == 2

    second = await client.get("/system/audit?limit=2&offset=2", headers=headers)
    assert second.status_code == 200
    assert len(second.json()) == 2
    # A page that repeats the previous one is not paging.
    assert {r["id"] for r in first.json()}.isdisjoint({r["id"] for r in second.json()})

    # The cap is a cap.
    assert (await client.get("/system/audit?limit=500", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_non_admin_cannot_verify_another_tenants_chain(client, db, operator):
    _, analyst = operator
    other_tenant, _ = await _operator(db)
    token = await _login(client, analyst.email)

    r = await client.get(
        f"/system/audit/verify?tenant_id={other_tenant.id}",
        headers=_bearer(client, token),
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_admin_can_verify_another_tenants_chain(client, db):
    _, admin = await _operator(db, role="admin")
    other_tenant, _ = await _operator(db)
    token = await _login(client, admin.email)

    r = await client.get(
        f"/system/audit/verify?tenant_id={other_tenant.id}",
        headers=_bearer(client, token),
    )
    assert r.status_code == 200, r.text
    # The parameter used to be ignored, which answered about the caller's own
    # tenant while looking like an answer about the one they named.
    assert r.json()["tenant_id"] == other_tenant.id


@pytest.mark.asyncio
async def test_audit_verify_defaults_to_the_callers_tenant(client, db, operator):
    tenant, user = operator
    token = await _login(client, user.email)
    r = await client.get("/system/audit/verify", headers=_bearer(client, token))
    assert r.status_code == 200, r.text
    assert r.json()["tenant_id"] == tenant.id
    assert r.json()["ok"] is True
