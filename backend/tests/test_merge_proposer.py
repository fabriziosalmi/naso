"""Integration: ``propose_and_merge`` turns shared-leak co-occurrence into
actual merges with evidence, via the new entity-resolution engine.

This replaces the legacy ``auto_merge_identities`` behaviour of merging on
the raw username prefix. Pairs of identities are now only merged if they
share one or more leaks — which is the strongest evidence NASO has.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from shared.domain.services.identity_upsert import upsert_identity
from shared.domain.services.merge_proposer import propose_and_merge
from shared.models import Identity, LeakHit, MergeEvent, identity_leaks

pytestmark = pytest.mark.asyncio


async def _make_leak(db, tenant_id, severity=50):
    leak = LeakHit(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        source="test",
        content_snippet=f"payload-{uuid.uuid4().hex[:8]}",
        severity_score=severity,
    )
    db.add(leak)
    await db.flush()
    return leak


async def _link(db, identity_id, leak_id):
    await db.execute(
        identity_leaks.insert().values(identity_id=identity_id, leak_id=leak_id)
    )


class TestMergesPairsSharingALeak:
    async def test_two_identities_in_one_leak_merge(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")

        leak = await _make_leak(corr_db, tenant.id, severity=80)
        await _link(corr_db, a.id, leak.id)
        await _link(corr_db, b.id, leak.id)
        await corr_db.commit()

        report = await propose_and_merge(corr_db, tenant.id)
        assert report["merged_count"] == 1

        # One of the two is now a slave of the other.
        rows = (
            await corr_db.execute(
                select(Identity).where(Identity.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert any(r.master_identity_id is not None for r in rows)


class TestNoSpuriousMerges:
    async def test_identities_without_shared_leaks_do_not_merge(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")

        # Each identity has its own leak — no co-occurrence.
        leak_a = await _make_leak(corr_db, tenant.id)
        leak_b = await _make_leak(corr_db, tenant.id)
        await _link(corr_db, a.id, leak_a.id)
        await _link(corr_db, b.id, leak_b.id)
        await corr_db.commit()

        report = await propose_and_merge(corr_db, tenant.id)
        assert report["merged_count"] == 0

        # Neither became a slave.
        await corr_db.refresh(a)
        await corr_db.refresh(b)
        assert a.master_identity_id is None
        assert b.master_identity_id is None


class TestIdempotencyAcrossCalls:
    async def test_calling_twice_does_not_re_merge(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")

        leak = await _make_leak(corr_db, tenant.id, severity=80)
        await _link(corr_db, a.id, leak.id)
        await _link(corr_db, b.id, leak.id)
        await corr_db.commit()

        r1 = await propose_and_merge(corr_db, tenant.id)
        r2 = await propose_and_merge(corr_db, tenant.id)

        assert r1["merged_count"] == 1
        # Second call: the pair no longer qualifies (one side is now a slave
        # so it is excluded from the "active master" population) — so zero
        # new merges, zero duplicate MergeEvent rows.
        assert r2["merged_count"] == 0

        events = (
            await corr_db.execute(
                select(MergeEvent).where(MergeEvent.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert len([e for e in events if e.reversed_at is None]) == 1


class TestMasterChoice:
    async def test_higher_risk_becomes_master(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "a@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "b@example.com", "email")
        # Set divergent risk so the choice is unambiguous.
        a.risk_score, b.risk_score = 30, 70
        await corr_db.commit()

        leak = await _make_leak(corr_db, tenant.id, severity=80)
        await _link(corr_db, a.id, leak.id)
        await _link(corr_db, b.id, leak.id)
        await corr_db.commit()

        await propose_and_merge(corr_db, tenant.id)
        await corr_db.refresh(a)
        await corr_db.refresh(b)

        # b had higher risk → b is master, a is subordinated.
        assert a.master_identity_id == b.id
        assert b.master_identity_id is None
