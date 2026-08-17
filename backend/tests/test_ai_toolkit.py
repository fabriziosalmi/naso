"""DB-backed tests for the AI tool dispatcher (shared.domain.services.ai_toolkit).

Each test constructs a fresh in-memory tenant, exercises one tool via
``execute_tool``, and asserts on the returned dict. No FastAPI, no LLM —
just the tool logic against a real AsyncSession, the same way the
agentic loop will call it.

Covers the 5 new tools introduced in Phase 8 plus tenant-isolation checks
on the existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from sqlalchemy import select

from shared.domain.services.ai_toolkit import execute_tool
from shared.domain.services.entity_resolution import merge_identities
from shared.domain.services.identity_upsert import upsert_identity
from shared.domain.services.leak_ingest import ingest_leak
from shared.models import identity_leaks
from shared.utils.audit_chain import write_audit

pytestmark = pytest.mark.asyncio


@dataclass
class FakeUser:
    """Minimal user object — the tool dispatcher only reads these fields."""

    id: str
    tenant_id: str
    role: str = "analyst"


SHARED_EVIDENCE = [{"type": "shared_leak", "leak_id": "leak-demo", "strength": 0.9}]


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _link(db, identity_id: str, leak_id: str) -> None:
    await db.execute(identity_leaks.insert().values(identity_id=identity_id, leak_id=leak_id))


# ═════════════════════════════════════════════════════════════════════════════
#   Existing tools — spot-check tenant isolation still works after refactor
# ═════════════════════════════════════════════════════════════════════════════


class TestSearchIdentities:
    async def test_non_admin_sees_only_own_tenant(self, corr_db, tenant, user):
        await upsert_identity(corr_db, tenant.id, "mine@example.com", "email")
        # An identity from a different tenant must be invisible.
        from shared.models import Tenant

        other_tenant = Tenant(id=str(uuid4()), name=f"other-{uuid4().hex[:6]}")
        corr_db.add(other_tenant)
        await corr_db.commit()
        await upsert_identity(corr_db, other_tenant.id, "theirs@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("search_identities", {}, corr_db, fake, None)
        identifiers = {d["identifier"] for d in result["data"]}
        assert "mine@example.com" in identifiers
        assert "theirs@example.com" not in identifiers

    async def test_empty_result_reports_the_types_that_exist(self, corr_db, tenant, user):
        # The regression: a model asked search_identities with type="person"
        # (what the UI's own dropdown writes), the ingested data was "email", it
        # got a bare empty list with no clue why, blamed the risk threshold, and
        # burned all five agent iterations lowering it. An empty result now
        # carries the vocabulary that actually exists, which turns the blind
        # retries into one corrected call.
        await upsert_identity(corr_db, tenant.id, "real@example.com", "email")
        fake = FakeUser(id=user.id, tenant_id=tenant.id)

        result = await execute_tool("search_identities", {"type": "person"}, corr_db, fake, None)

        assert result["count"] == 0
        assert "hint" in result
        assert "email" in result["hint"]

    async def test_a_matching_filter_carries_no_hint(self, corr_db, tenant, user):
        await upsert_identity(corr_db, tenant.id, "real@example.com", "email")
        fake = FakeUser(id=user.id, tenant_id=tenant.id)

        result = await execute_tool("search_identities", {"type": "email"}, corr_db, fake, None)

        assert result["count"] == 1
        assert "hint" not in result


# ═════════════════════════════════════════════════════════════════════════════
#   Phase 8 — new tools
# ═════════════════════════════════════════════════════════════════════════════


class TestGetMergeCluster:
    async def test_returns_root_and_slaves(self, corr_db, tenant, user):
        master = await upsert_identity(corr_db, tenant.id, "m@example.com", "email")
        slave1 = await upsert_identity(corr_db, tenant.id, "s1@example.com", "email")
        slave2 = await upsert_identity(corr_db, tenant.id, "s2@example.com", "email")
        await merge_identities(corr_db, master=master, slave=slave1, evidence=SHARED_EVIDENCE)
        await merge_identities(corr_db, master=master, slave=slave2, evidence=SHARED_EVIDENCE)

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("get_merge_cluster", {"identity_id": master.id}, corr_db, fake, None)

        assert "error" not in result
        assert result["root"]["id"] == master.id
        assert result["cluster_size"] == 3
        member_ids = {m["id"] for m in result["members"]}
        assert {master.id, slave1.id, slave2.id}.issubset(member_ids)
        slave_flags = {m["id"]: m["is_slave"] for m in result["members"]}
        assert slave_flags[master.id] is False
        assert slave_flags[slave1.id] is True
        assert slave_flags[slave2.id] is True
        assert len(result["recent_merges"]) == 2

    async def test_unknown_identity_returns_error(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("get_merge_cluster", {"identity_id": "not-a-real-id"}, corr_db, fake, None)
        assert "error" in result

    async def test_cross_tenant_is_hidden_from_non_admin(self, corr_db, tenant, user):
        from shared.models import Tenant

        other = Tenant(id=str(uuid4()), name=f"other-{uuid4().hex[:6]}")
        corr_db.add(other)
        await corr_db.commit()
        foreign = await upsert_identity(corr_db, other.id, "elsewhere@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)  # analyst, not admin
        result = await execute_tool("get_merge_cluster", {"identity_id": foreign.id}, corr_db, fake, None)
        # "not found" — we do not leak the existence of the row.
        assert "error" in result


class TestProposeMergesPreview:
    async def test_lists_pairs_sharing_a_leak(self, corr_db, tenant, user):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")
        leak = await ingest_leak(corr_db, tenant_id=tenant.id, source="test", content="demo payload", severity_score=80)
        await _link(corr_db, a.id, leak.id)
        await _link(corr_db, b.id, leak.id)
        await corr_db.commit()

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("propose_merges_preview", {}, corr_db, fake, None)

        assert result["count"] >= 1
        pair = result["pairs"][0]
        assert pair["master_id"] in {a.id, b.id}
        assert pair["slave_id"] in {a.id, b.id}
        assert pair["master_id"] != pair["slave_id"]
        assert pair["confidence"] >= 0.5
        assert pair["shared_leak_count"] == 1

    async def test_no_pairs_when_no_shared_leaks(self, corr_db, tenant, user):
        await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        await upsert_identity(corr_db, tenant.id, "b@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("propose_merges_preview", {}, corr_db, fake, None)
        assert result["count"] == 0

    async def test_preview_does_not_execute(self, corr_db, tenant, user):
        """The whole point of the preview is that nothing changes."""
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")
        leak = await ingest_leak(corr_db, tenant_id=tenant.id, source="test", content="demo", severity_score=80)
        await _link(corr_db, a.id, leak.id)
        await _link(corr_db, b.id, leak.id)
        await corr_db.commit()

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        await execute_tool("propose_merges_preview", {}, corr_db, fake, None)

        await corr_db.refresh(a)
        await corr_db.refresh(b)
        assert a.master_identity_id is None
        assert b.master_identity_id is None


class TestVerifyAuditChain:
    async def test_reports_ok_on_pristine_chain(self, corr_db, tenant, user):
        for i in range(3):
            await write_audit(
                corr_db,
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"TEST_{i}",
                resource_type="x",
                resource_id=str(i),
                details={"i": i},
            )

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("verify_audit_chain", {}, corr_db, fake, None)

        assert result["ok"] is True
        assert result["broken_at"] is None

    async def test_reports_break_when_tampered(self, corr_db, tenant, user):
        for i in range(3):
            await write_audit(
                corr_db,
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"TEST_{i}",
                resource_type="x",
                resource_id=str(i),
                details={"i": i},
            )

        # Tamper with the middle row.
        from shared.models import AuditLog

        chain = (
            (
                await corr_db.execute(
                    select(AuditLog).where(AuditLog.tenant_id == tenant.id).order_by(AuditLog.timestamp, AuditLog.id)
                )
            )
            .scalars()
            .all()
        )
        chain[1].details = {"tampered": True}
        await corr_db.commit()

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("verify_audit_chain", {}, corr_db, fake, None)

        assert result["ok"] is False
        assert result["broken_at"] == 1


class TestFindNearDuplicates:
    SAMPLE = "password leak for acme corp, 14000 records, forum breach 2023"

    async def test_finds_near_duplicate(self, corr_db, tenant, user):
        await ingest_leak(corr_db, tenant_id=tenant.id, source="test", content=self.SAMPLE, severity_score=70)

        variant = "  Password leak for ACME Corp.  14000 records, forum breach 2023  "
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("find_near_duplicates", {"content": variant}, corr_db, fake, None)

        assert result["match_count"] >= 1
        assert result["matches"][0]["distance"] <= 5

    async def test_no_matches_for_unrelated_content(self, corr_db, tenant, user):
        await ingest_leak(corr_db, tenant_id=tenant.id, source="test", content=self.SAMPLE, severity_score=70)

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool(
            "find_near_duplicates",
            {"content": "cryptocurrency wallet addresses dumped from discord channel"},
            corr_db,
            fake,
            None,
        )
        assert result["match_count"] == 0

    async def test_missing_content_returns_error(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("find_near_duplicates", {}, corr_db, fake, None)
        assert "error" in result


class TestMergeEventsHistory:
    async def test_returns_merges_for_identity(self, corr_db, tenant, user):
        master = await upsert_identity(corr_db, tenant.id, "m@example.com", "email")
        slave = await upsert_identity(corr_db, tenant.id, "s@example.com", "email")
        event = await merge_identities(corr_db, master=master, slave=slave, evidence=SHARED_EVIDENCE)

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("get_merge_events_history", {"identity_id": master.id}, corr_db, fake, None)

        assert result["count"] == 1
        entry = result["events"][0]
        assert entry["id"] == event.id
        assert entry["master_id"] == master.id
        assert entry["slave_id"] == slave.id
        assert entry["reversed_at"] is None

    async def test_returns_all_tenant_merges_when_identity_omitted(self, corr_db, tenant, user):
        for _ in range(3):
            m = await upsert_identity(corr_db, tenant.id, f"m-{uuid4().hex[:6]}@example.com", "email")
            s = await upsert_identity(corr_db, tenant.id, f"s-{uuid4().hex[:6]}@example.com", "email")
            await merge_identities(corr_db, master=m, slave=s, evidence=SHARED_EVIDENCE)

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("get_merge_events_history", {}, corr_db, fake, None)
        assert result["count"] == 3


class TestUnknownTool:
    async def test_returns_error_for_unknown_tool(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        result = await execute_tool("no_such_tool", {}, corr_db, fake, None)
        assert "error" in result
        assert "Unknown tool" in result["error"]
