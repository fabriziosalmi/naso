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

The second half of the file widens that from one route to the whole app: it
probes every documented operation anonymously and fails if anything outside a
four-entry allow-list answers. Same principle, applied to the authentication
boundary rather than the tenant one.
"""

import re
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
# Four routes answer without credentials, and each is deliberate:
#
#   POST /auth/login    the SPA has to bootstrap somehow
#   POST /auth/logout   takes an optional bearer and clears the cookie either
#                       way, so an anonymous caller gets 200 and nothing else;
#                       it removes credentials, it never returns data
#   GET  /system/status  orchestrators and load balancers hold no credentials
#   GET  /system/health
#
# Anything else answering is a regression, and /ai/health was one — it returned
# AI_ENDPOINT, the model inventory and the raw connection error to anyone.
#
# The enumeration is the point. Asserting that one known-bad route is now closed
# proves one route was fixed; it says nothing about the fifth route someone adds
# next month. Comparing the *whole* surface against an explicit allow-list is
# what makes this a boundary rather than a spot check.
#
# Two design notes, both bought with a failure:
#
# 1. This drives real HTTP rather than introspecting the router. The first
#    version walked `app.routes` looking for an auth dependency in each route's
#    dependency tree. FastAPI 0.141 stores each included router as an opaque
#    `fastapi.routing._IncludedRouter` with no `.routes` and no `.dependant`, so
#    the walk found the four docs endpoints, matched nothing, and reported an
#    empty set — a boundary test that silently measured nothing while reading as
#    coverage. A behavioural probe cannot fail that way, and it tests the
#    property we actually care about ("does it answer?") rather than a proxy for
#    it ("does it mention get_current_user?"). It also owes nothing to FastAPI
#    internals, which matters because requirements.txt pins `fastapi>=0.111.0`
#    with no ceiling.
#
# 2. `_ROUTE_FLOOR` exists so that enumerating nothing fails loudly. If a future
#    refactor empties the OpenAPI schema, every assertion below becomes vacuous
#    and the suite goes green on zero coverage. That is the exact failure mode
#    this test was rewritten to escape, so it is asserted rather than assumed.

PUBLIC_SURFACE = {
    "POST /auth/login",
    "POST /auth/logout",
    "GET /system/status",
    "GET /system/health",
}

# The app currently exposes 49 documented operations. The floor is deliberately
# slack — it is a tripwire against enumerating nothing, not a route count to
# keep updated on every PR.
_ROUTE_FLOOR = 40

_PROBE_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _documented_operations():
    """Every (method, path) in the OpenAPI schema — the app's own public API."""
    from app.main import app

    for path, operations in sorted(app.openapi()["paths"].items()):
        for method in sorted(operations):
            if method.upper() in _PROBE_METHODS:
                yield method.upper(), path


@pytest.mark.asyncio
async def test_the_unauthenticated_surface_is_exactly_these_four(client):
    """Probe every documented route anonymously; only the allow-list may answer."""
    operations = list(_documented_operations())
    assert len(operations) >= _ROUTE_FLOOR, (
        f"only {len(operations)} routes enumerated, expected at least {_ROUTE_FLOOR}. "
        "The schema is empty or truncated, so this test is not checking anything."
    )

    answered, refused_oddly = [], []
    for method, path in operations:
        name = f"{method} {path}"
        if name in PUBLIC_SURFACE:
            # Deliberately open; its behaviour is asserted elsewhere. Skipped
            # before the probe so that a public route legitimately raising
            # cannot be misfiled as a leak below.
            continue
        # Path params are never reached: auth is resolved before the handler, so
        # a syntactically valid placeholder is enough to get past routing.
        concrete = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
        client.cookies.clear()
        try:
            response = await client.request(
                method,
                concrete,
                json={} if method in {"POST", "PUT", "PATCH"} else None,
            )
        except Exception as exc:  # noqa: BLE001 — any escape means the handler ran
            # An unguarded handler that reaches for a backing service raises
            # rather than returning a status. That is still the finding: the
            # request got past auth into application code. Catching it here
            # keeps the failure legible instead of a transport traceback.
            answered.append(f"{name} -> handler executed and raised {type(exc).__name__}")
            continue
        # 401 (no credentials) and 403 (credentials rejected) are both refusals.
        # Anything else — including 422 — means the request was parsed before it
        # was authorised, which leaks schema shape to an anonymous caller.
        if response.status_code < 400:
            answered.append(f"{name} -> {response.status_code}")
        elif response.status_code not in (401, 403):
            refused_oddly.append(f"{name} -> {response.status_code}")

    assert not answered, "guarded routes answered an anonymous caller:\n  " + "\n  ".join(answered)
    assert not refused_oddly, (
        "guarded routes rejected anonymously, but not with 401/403 — auth ran "
        "after input parsing:\n  " + "\n  ".join(refused_oddly)
    )


@pytest.mark.asyncio
async def test_every_route_on_the_allow_list_still_exists(client):
    """The allow-list is only a boundary if its entries are real routes.

    Without this, deleting `/system/health` would leave a stale name in
    PUBLIC_SURFACE that permanently excuses whatever route later takes it.
    """
    documented = {f"{method} {path}" for method, path in _documented_operations()}
    missing = PUBLIC_SURFACE - documented
    assert not missing, f"allow-list names routes that no longer exist: {sorted(missing)}"


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
