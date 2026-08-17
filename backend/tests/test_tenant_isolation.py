"""Cross-tenant authorization on the investigation-plan endpoints.

SECURITY.md states that queries filter on the tenant embedded in the caller's
token rather than on anything the caller supplies. `PATCH
/ai/plans/{plan_id}/tasks/{task_id}` did not: it selected the task by id and
plan id alone, so `current_user` authenticated the caller and then never
authorised them. Any logged-in operator — any tenant, any role — could rewrite
another tenant's investigation task by naming its id.

Seven of the eight plan endpoints already scoped by
`InvestigationPlan.tenant_id`; that one did not. These tests exist so the odd
one out cannot drift back, and so the claim in SECURITY.md is backed by
something executable rather than by inspection.
"""

import uuid

import pytest
import pytest_asyncio

from shared.core.security import get_password_hash
from shared.models import InvestigationPlan, InvestigationTask, Tenant, User


async def _make_tenant(db, label):
    tenant = Tenant(id=str(uuid.uuid4()), name=f"{label}-{uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    user = User(
        id=str(uuid.uuid4()),
        email=f"{label}-{uuid.uuid4().hex[:6]}@naso.example.com",
        hashed_password=get_password_hash("Str0ng&Pass!"),
        tenant_id=tenant.id,
        role="analyst",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return tenant, user


@pytest_asyncio.fixture
async def two_tenants(db):
    """Victim tenant owning a plan and a task, plus an unrelated attacker."""
    victim_tenant, victim_user = await _make_tenant(db, "victim")
    attacker_tenant, attacker_user = await _make_tenant(db, "attacker")

    plan = InvestigationPlan(
        id=str(uuid.uuid4()),
        tenant_id=victim_tenant.id,
        user_id=victim_user.id,
        title="Operation Kingfisher",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    task = InvestigationTask(
        id=str(uuid.uuid4()),
        plan_id=plan.id,
        content="Confirm the broker's alias before escalating",
        status="pending",
        created_by="user",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return {
        "plan": plan,
        "task": task,
        "victim": victim_user,
        "attacker": attacker_user,
    }


async def _login(client, email, password="Str0ng&Pass!"):
    r = await client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(client, token):
    # The suite's client keeps cookies between requests; a leftover session
    # cookie would make CSRFMiddleware, not authorization, decide the outcome.
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_other_tenant_cannot_patch_a_task(client, db, two_tenants):
    plan, task, attacker = two_tenants["plan"], two_tenants["task"], two_tenants["attacker"]
    token = await _login(client, attacker.email)

    r = await client.patch(
        f"/ai/plans/{plan.id}/tasks/{task.id}",
        json={"status": "completed", "content": "closed, nothing to see"},
        headers=_bearer(client, token),
    )

    # 404, not 403: confirming the task exists but belongs to someone else is
    # itself a disclosure.
    assert r.status_code == 404, f"cross-tenant PATCH was accepted: {r.status_code} {r.text}"

    await db.refresh(task)
    assert task.status == "pending"
    assert task.content == "Confirm the broker's alias before escalating"


@pytest.mark.asyncio
async def test_owning_tenant_can_still_patch_its_task(client, db, two_tenants):
    # The fix must not close the door on the legitimate caller.
    plan, task, victim = two_tenants["plan"], two_tenants["task"], two_tenants["victim"]
    token = await _login(client, victim.email)

    r = await client.patch(
        f"/ai/plans/{plan.id}/tasks/{task.id}",
        json={"status": "completed"},
        headers=_bearer(client, token),
    )
    assert r.status_code == 200, r.text

    await db.refresh(task)
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_unauthenticated_patch_is_rejected(client, two_tenants):
    plan, task = two_tenants["plan"], two_tenants["task"]
    client.cookies.clear()
    r = await client.patch(
        f"/ai/plans/{plan.id}/tasks/{task.id}",
        json={"status": "completed"},
    )
    assert r.status_code == 401


# ── Unauthenticated surface ─────────────────────────────────────────────────
#
# Exactly three routes answer without credentials, and each is deliberate:
# /auth/login (the SPA has to bootstrap somehow), /system/status and
# /system/health (orchestrators and load balancers hold none). Anything else
# appearing here is a regression, and /ai/health was one — it returned
# AI_ENDPOINT, the model inventory and the raw connection error to anyone.


@pytest.mark.asyncio
async def test_ai_health_requires_authentication(client):
    client.cookies.clear()
    r = await client.get("/ai/health")
    assert r.status_code == 401, f"/ai/health answered anonymously: {r.status_code} {r.text[:200]}"


@pytest.mark.asyncio
async def test_ai_health_never_leaks_the_exception_text(client, two_tenants):
    # Nothing is listening on AI_ENDPOINT during the suite, so this exercises
    # the failure path — which is the one that used to echo str(e) back.
    token = await _login(client, two_tenants["victim"].email)
    r = await client.get("/ai/health", headers=_bearer(client, token))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "offline"
    assert "error" not in body
    for leaky in ("Traceback", "ConnectError", "Connection refused", "Errno"):
        assert leaky not in r.text, f"exception detail leaked to the client: {leaky}"
