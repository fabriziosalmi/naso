"""Contract tests for the near-duplicate leak dedup layer.

Exact SHA-256 dedup already exists in the legacy pipeline (good). The rewrite
adds a SimHash layer so whitespace / punctuation / encoding variants of the
same leak collapse into a single row — critical once we start ingesting from
multiple overlapping sources (GitHub raw vs gist, Telegram forward vs origin).

Contracts:

  * ``ingest_leak`` sets ``normalized_content`` and ``simhash64`` on every row.
  * Ingesting the same content twice returns the same ``LeakHit`` (exact dedup).
  * Ingesting a near-duplicate (Hamming ≤ 3) returns the existing row and
    optionally bumps ``severity_score`` if the new occurrence scores higher.
  * Ingesting a genuinely different leak creates a new row.
  * The dedup query is tenant-scoped — two tenants can hold the same content.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from shared.models import LeakHit

pytest.importorskip("shared.domain.services.leak_ingest", reason="Phase 5 not implemented yet")
from shared.domain.services.leak_ingest import ingest_leak  # noqa: E402


pytestmark = pytest.mark.asyncio


SAMPLE = (
    "password leak for acme corp, 14000 records, including emails and hashed "
    "passwords from the forum breach of 2023"
)


async def _count(db, tenant_id):
    rows = (
        await db.execute(select(LeakHit).where(LeakHit.tenant_id == tenant_id))
    ).scalars().all()
    return len(rows)


class TestFingerprintPopulation:
    async def test_normalized_content_and_simhash_are_set(self, corr_db, tenant):
        leak = await ingest_leak(
            corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70
        )
        assert leak.normalized_content, "normalization must persist"
        assert leak.simhash64 is not None


class TestExactDedup:
    async def test_same_content_returns_same_row(self, corr_db, tenant):
        a = await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70)
        b = await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70)
        assert a.id == b.id
        assert await _count(corr_db, tenant.id) == 1


class TestNearDup:
    async def test_whitespace_variant_dedups(self, corr_db, tenant):
        await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70)

        variant = (
            "  Password leak for ACME corp.  14000 records, including emails and hashed "
            "passwords from the forum breach of 2023  "
        )
        await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=variant, severity_score=72)

        assert await _count(corr_db, tenant.id) == 1, (
            "whitespace/casing variants must be recognised as near-duplicates"
        )

    async def test_near_dup_bumps_severity_when_higher(self, corr_db, tenant):
        first = await ingest_leak(
            corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=50
        )
        variant = SAMPLE.upper()
        second = await ingest_leak(
            corr_db, tenant_id=tenant.id, source="github", content=variant, severity_score=80
        )
        assert first.id == second.id
        await corr_db.refresh(first)
        assert first.severity_score == 80

    async def test_near_dup_does_not_downgrade_severity(self, corr_db, tenant):
        first = await ingest_leak(
            corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=80
        )
        await ingest_leak(
            corr_db, tenant_id=tenant.id, source="github", content=SAMPLE.upper(), severity_score=30
        )
        await corr_db.refresh(first)
        assert first.severity_score == 80


class TestGenuinelyDifferentContent:
    async def test_different_content_creates_new_row(self, corr_db, tenant):
        await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70)
        await ingest_leak(
            corr_db,
            tenant_id=tenant.id,
            source="github",
            content="cryptocurrency wallet addresses dumped from discord channel",
            severity_score=60,
        )
        assert await _count(corr_db, tenant.id) == 2


class TestTenantIsolation:
    async def test_same_content_in_two_tenants_is_two_rows(self, corr_db, tenant):
        from shared.models import Tenant
        import uuid as _uuid

        other = Tenant(id=str(_uuid.uuid4()), name=f"other-{_uuid.uuid4().hex[:6]}")
        corr_db.add(other)
        await corr_db.commit()

        await ingest_leak(corr_db, tenant_id=tenant.id, source="github", content=SAMPLE, severity_score=70)
        await ingest_leak(corr_db, tenant_id=other.id, source="github", content=SAMPLE, severity_score=70)

        assert await _count(corr_db, tenant.id) == 1
        assert await _count(corr_db, other.id) == 1
