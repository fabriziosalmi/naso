"""The MCP server: does it import, and does it stay inside one tenant.

Two defects, both invisible because nothing ever imported this module.

**It did not import.** The server was written against the `@app.list_tools()` /
`@app.call_tool()` decorators of an early `mcp` release; `requirements.txt` pins
`mcp>=1.28.1` with no ceiling, and against the 2.0.0 that resolves to,

    AttributeError: 'Server' object has no attribute 'list_tools'

at import. The docs advertise this feature on the home page and give it a guide
page. `test_the_module_imports` is the whole point of that first test: it fails
on the pristine file.

**It was unscoped.** Every query ran without a tenant filter —
`select(Identity).limit(limit)`, `select(LeakHit).where(severity >= …)` — so it
returned every tenant's identities and leak snippets to whoever drove the client,
and `naso_protect_identity` selected by id alone and then wrote. The HTTP API
filters all three on the caller's tenant.
"""

import uuid
from datetime import datetime, timezone

import pytest

from shared.models import Identity, LeakHit, Tenant


@pytest.fixture
def mcp():
    """The server module.

    `conftest.py` puts the repository root and `backend/` on `sys.path`, and the
    API image copies the contents of `backend/` to `/app`, so the module name is
    `mcp_server` in both places.
    """
    return pytest.importorskip("mcp_server", reason="the mcp SDK is not installed here")


@pytest.fixture
def bound(mcp, db, monkeypatch):
    """Two tenants with data, the module pointed at the test session, one tenant bound."""

    async def _one_session():
        yield db

    monkeypatch.setattr(mcp, "get_db_session", _one_session, raising=True)

    async def _setup():
        rows = {}
        for label in ("ours", "theirs"):
            tenant = Tenant(id=str(uuid.uuid4()), name=f"{label}-{uuid.uuid4().hex[:6]}")
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)

            identity = Identity(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                identifier=f"{label}@naso.example.com",
                type="email",
                risk_score=50,
            )
            leak = LeakHit(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                source=f"{label}-source",
                severity_score=95,
                status="new",
                content_snippet=f"{label} snippet",
                discovered_at=datetime.now(timezone.utc),
            )
            db.add_all([identity, leak])
            await db.commit()
            rows[label] = {"tenant": tenant, "identity": identity, "leak": leak}
        monkeypatch.setenv("NASO_MCP_TENANT_ID", rows["ours"]["tenant"].id)
        return rows

    return _setup


def test_the_module_imports(mcp):
    """Fails on the pristine file with AttributeError from the SDK."""
    assert hasattr(mcp, "server")
    tools = {
        "naso_darkweb_recon",
        "naso_shodan_scan",
        "naso_telegram_intel",
        "naso_get_identities",
        "naso_get_leaks",
        "naso_protect_identity",
    }
    assert tools <= set(dir(mcp))


@pytest.mark.asyncio
async def test_identities_are_scoped_to_the_bound_tenant(mcp, bound):
    await bound()
    out = await mcp.naso_get_identities(limit=50)
    assert "ours@naso.example.com" in out
    assert "theirs@naso.example.com" not in out


@pytest.mark.asyncio
async def test_leaks_are_scoped_to_the_bound_tenant(mcp, bound):
    await bound()
    out = await mcp.naso_get_leaks(min_severity=0)
    assert "ours snippet" in out
    # Leak snippets are the payload itself — breach text, credentials, PII.
    assert "theirs snippet" not in out


@pytest.mark.asyncio
async def test_protect_identity_cannot_write_across_tenants(mcp, bound, db):
    rows = await bound()
    victim = rows["theirs"]["identity"]

    out = await mcp.naso_protect_identity(identity_id=victim.id, is_protected=True)

    assert "not found" in out.lower()
    await db.refresh(victim)
    assert victim.is_protected is not True


def test_the_server_refuses_to_start_without_a_tenant(mcp, monkeypatch):
    monkeypatch.delenv("NASO_MCP_TENANT_ID", raising=False)
    with pytest.raises(RuntimeError, match="NASO_MCP_TENANT_ID"):
        mcp.mcp_tenant_id()

    # Whitespace is not a tenant id either.
    monkeypatch.setenv("NASO_MCP_TENANT_ID", "   ")
    with pytest.raises(RuntimeError, match="NASO_MCP_TENANT_ID"):
        mcp.mcp_tenant_id()
