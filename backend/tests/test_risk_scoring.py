"""Contract tests for the new lazy risk-scoring service.

The legacy service recomputes on demand with no invalidation strategy, leaving
masters with stale scores after merges. The rewrite's contract:

  * Any mutation that could affect risk (new leak link, merge, unmerge) flips
    ``identity.risk_score_dirty = True`` for the affected rows — cheap,
    write-side, transactional.
  * A separate ``recompute_dirty`` pass (worker / endpoint) reads the dirty
    set, recomputes scores, clears the flag.
  * Merging propagates the dirty flag up to the master.
  * Recompute traverses the merge hierarchy — a master's risk reflects the
    union of its own and its slaves' linked leaks.
  * Reversing a merge re-marks both master and slave dirty.
"""

from __future__ import annotations

import pytest

from shared.models import LeakHit, identity_leaks

pytest.importorskip("shared.domain.services.risk_scoring_v2", reason="Phase 4 not implemented yet")
from shared.domain.services.entity_resolution import merge_identities, reverse_merge  # noqa: E402
from shared.domain.services.identity_upsert import upsert_identity  # noqa: E402
from shared.domain.services.risk_scoring_v2 import (  # noqa: E402
    compute_risk_for_identity,
    mark_dirty,
    recompute_dirty,
)

pytestmark = pytest.mark.asyncio


EV = [{"type": "shared_leak", "leak_id": "demo", "strength": 0.9}]


async def _attach_leak(db, tenant_id, identity, severity, source="test"):
    import uuid as _uuid

    leak = LeakHit(
        id=str(_uuid.uuid4()),
        tenant_id=tenant_id,
        source=source,
        content_snippet=f"payload-{_uuid.uuid4().hex[:6]}",
        severity_score=severity,
    )
    db.add(leak)
    await db.flush()
    await db.execute(identity_leaks.insert().values(identity_id=identity.id, leak_id=leak.id))
    await db.commit()
    return leak


class TestDirtyFlagPropagation:
    async def test_new_leak_link_marks_identity_dirty(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        await _attach_leak(corr_db, tenant.id, ident, severity=75)
        await mark_dirty(corr_db, [ident.id])

        await corr_db.refresh(ident)
        assert ident.risk_score_dirty is True

    async def test_merge_marks_master_dirty(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")
        await merge_identities(corr_db, master=a, slave=b, evidence=EV)
        await corr_db.refresh(a)
        assert a.risk_score_dirty is True, "merging a slave must dirty the master"

    async def test_reverse_merge_dirties_both_sides(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")
        event = await merge_identities(corr_db, master=a, slave=b, evidence=EV)

        # Clear dirty after first recompute cycle.
        await recompute_dirty(corr_db, tenant.id)
        await corr_db.refresh(a)
        await corr_db.refresh(b)
        assert a.risk_score_dirty is False
        assert b.risk_score_dirty is False

        await reverse_merge(corr_db, event, reason="test")
        await corr_db.refresh(a)
        await corr_db.refresh(b)
        assert a.risk_score_dirty is True
        assert b.risk_score_dirty is True


class TestRecomputeClearsDirty:
    async def test_recompute_clears_dirty_flag(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        await _attach_leak(corr_db, tenant.id, ident, severity=60)
        await mark_dirty(corr_db, [ident.id])

        await recompute_dirty(corr_db, tenant.id)
        await corr_db.refresh(ident)
        assert ident.risk_score_dirty is False
        assert ident.risk_score > 0, "risk score should reflect the attached leak"


class TestMergeCascade:
    async def test_master_score_reflects_slaves_leaks(self, corr_db, tenant):
        """After merging slave into master, recomputing master includes
        severity signals from all slave-linked leaks."""
        master = await upsert_identity(corr_db, tenant.id, "master@example.com", "email")
        slave = await upsert_identity(corr_db, tenant.id, "slave@example.com", "email")

        # Only the slave has leaks attached directly.
        await _attach_leak(corr_db, tenant.id, slave, severity=90)
        await _attach_leak(corr_db, tenant.id, slave, severity=85)

        # Score the master BEFORE merge — should be zero (no direct leaks).
        await mark_dirty(corr_db, [master.id])
        await recompute_dirty(corr_db, tenant.id)
        await corr_db.refresh(master)
        pre_merge = master.risk_score
        assert pre_merge == 0

        # Merge, recompute, verify master's score now reflects slave's leaks.
        await merge_identities(corr_db, master=master, slave=slave, evidence=EV)
        await recompute_dirty(corr_db, tenant.id)
        await corr_db.refresh(master)
        assert master.risk_score > pre_merge, "after merge, master risk must include slave's leaks"


class TestBoundedness:
    async def test_risk_never_exceeds_100(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "hot@example.com", "email")
        # Pile on many critical leaks.
        for _ in range(20):
            await _attach_leak(corr_db, tenant.id, ident, severity=100)
        await mark_dirty(corr_db, [ident.id])
        await recompute_dirty(corr_db, tenant.id)
        await corr_db.refresh(ident)
        assert 0 <= ident.risk_score <= 100


class TestPureComputeIsReadOnly:
    async def test_compute_risk_for_identity_does_not_write(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        await _attach_leak(corr_db, tenant.id, ident, severity=70)

        score = await compute_risk_for_identity(corr_db, ident.id)
        # Pure read: dirty flag untouched, stored score untouched.
        await corr_db.refresh(ident)
        assert ident.risk_score_dirty is False
        assert ident.risk_score == 0, "compute is a pure read; it must not persist"
        assert score > 0
