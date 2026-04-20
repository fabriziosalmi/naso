"""Contract tests for the new EntityResolutionService (merge engine).

The legacy ``IdentityMergingService.auto_merge_identities`` merges on raw
username prefix, inflates risk scores on repeat calls, has no undo, and
silently allows VIP demotion. These tests encode the rewrite's contract:

  * Evidence-gated — no evidence ⇒ no merge.
  * Idempotent — merging the same pair twice is a no-op second time.
  * VIP-protecting invariant — a protected slave cannot be subordinated
    under a non-protected master without promoting the master (or the merge
    is rejected, depending on policy — we assert the invariant outcome).
  * Reversible — ``reverse_merge`` restores the slave's independence.
  * Tenant-isolated — merges across tenants are forbidden.
  * Audit-logged — every merge creates an append-only ``MergeEvent`` with a
    hash chain.

All tests start RED until Phase 3 implements the service.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from shared.models import Identity, MergeEvent

pytest.importorskip("shared.domain.services.entity_resolution", reason="Phase 3 not implemented yet")
from shared.domain.services.entity_resolution import (  # noqa: E402
    merge_identities,
    reverse_merge,
    InsufficientEvidence,
    CrossTenantMerge,
    VipInvariantViolation,
)
from shared.domain.services.identity_upsert import upsert_identity  # noqa: E402


pytestmark = pytest.mark.asyncio


SHARED_LEAK_EVIDENCE = [
    {"type": "shared_leak", "leak_id": "leak-abc", "strength": 0.9},
]


async def _make_pair(db, tenant_id, ids=("a@example.com", "b@example.com")):
    a = await upsert_identity(db, tenant_id, ids[0], "email")
    b = await upsert_identity(db, tenant_id, ids[1], "email")
    return a, b


class TestEvidenceRequired:
    async def test_merge_without_evidence_is_rejected(self, corr_db, tenant):
        a, b = await _make_pair(corr_db, tenant.id)
        with pytest.raises(InsufficientEvidence):
            await merge_identities(corr_db, master=a, slave=b, evidence=[])

    async def test_merge_with_weak_evidence_is_rejected(self, corr_db, tenant):
        """A single signal below the confidence threshold must not auto-merge."""
        a, b = await _make_pair(corr_db, tenant.id)
        weak = [{"type": "username_prefix_match", "strength": 0.2}]
        with pytest.raises(InsufficientEvidence):
            await merge_identities(corr_db, master=a, slave=b, evidence=weak)


class TestIdempotency:
    async def test_merging_same_pair_twice_is_noop(self, corr_db, tenant):
        a, b = await _make_pair(corr_db, tenant.id)
        first = await merge_identities(
            corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
        )
        second = await merge_identities(
            corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
        )
        assert first.id == second.id, "second merge should return the existing event"

        events = (await corr_db.execute(select(MergeEvent))).scalars().all()
        active = [e for e in events if e.reversed_at is None]
        assert len(active) == 1

    async def test_repeat_merge_does_not_inflate_risk(self, corr_db, tenant):
        """Regression guard for the legacy bug where risk += slave//2 on each call."""
        a, b = await _make_pair(corr_db, tenant.id)
        a.risk_score, b.risk_score = 40, 60
        await corr_db.commit()

        await merge_identities(corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE)
        await corr_db.refresh(a)
        after_first = a.risk_score

        await merge_identities(corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE)
        await corr_db.refresh(a)

        assert a.risk_score == after_first, "risk must not accumulate on idempotent replay"


class TestVipInvariant:
    async def test_protected_slave_under_unprotected_master_violates_invariant(
        self, corr_db, tenant
    ):
        a, b = await _make_pair(corr_db, tenant.id)
        a.is_protected = False
        b.is_protected = True
        await corr_db.commit()

        # Policy we are encoding: the engine either promotes the master to
        # protected, or rejects the merge outright. Both are acceptable; what
        # is NOT acceptable is the slave silently losing protection.
        try:
            event = await merge_identities(
                corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
            )
        except VipInvariantViolation:
            return  # acceptable outcome: refuse to merge
        # If the merge was accepted, the master MUST now carry protection.
        await corr_db.refresh(a)
        assert a.is_protected is True, (
            "accepting a VIP-slave merge requires promoting the master to protected"
        )
        assert event is not None


class TestCrossTenant:
    async def test_cross_tenant_merge_rejected(self, corr_db, corr_session_factory, tenant):
        from shared.models import Tenant
        import uuid as _uuid

        other = Tenant(id=str(_uuid.uuid4()), name=f"other-{_uuid.uuid4().hex[:6]}")
        corr_db.add(other)
        await corr_db.commit()

        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, other.id, "b@example.com", "email")

        with pytest.raises(CrossTenantMerge):
            await merge_identities(
                corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
            )


class TestReversibility:
    async def test_reverse_merge_restores_independence(self, corr_db, tenant):
        a, b = await _make_pair(corr_db, tenant.id)
        event = await merge_identities(
            corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
        )
        await corr_db.refresh(b)
        assert b.master_identity_id == a.id

        await reverse_merge(corr_db, event, reason="test reversal")

        await corr_db.refresh(b)
        assert b.master_identity_id is None
        await corr_db.refresh(event)
        assert event.reversed_at is not None
        assert event.reverse_reason == "test reversal"


class TestAuditLedger:
    async def test_merge_event_has_hash_chain_link(self, corr_db, tenant):
        a, b = await _make_pair(corr_db, tenant.id)
        first = await merge_identities(
            corr_db, master=a, slave=b, evidence=SHARED_LEAK_EVIDENCE
        )
        assert first.self_hash, "every merge event must carry a self_hash"

        # Second merge in the same tenant should reference the first as prev_hash.
        c = await upsert_identity(corr_db, tenant.id, "c@example.com", "email")
        d = await upsert_identity(corr_db, tenant.id, "d@example.com", "email")
        second = await merge_identities(
            corr_db, master=c, slave=d, evidence=SHARED_LEAK_EVIDENCE
        )
        assert second.prev_hash == first.self_hash, "merge ledger must be hash-chained"


class TestSelfMergeRejected:
    async def test_cannot_merge_identity_with_itself(self, corr_db, tenant):
        a, _ = await _make_pair(corr_db, tenant.id)
        with pytest.raises(ValueError):
            await merge_identities(
                corr_db, master=a, slave=a, evidence=SHARED_LEAK_EVIDENCE
            )
