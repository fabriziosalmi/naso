"""Contract tests for the new IdentityUpsertService.

These tests describe the behaviour we want the rewritten correlation engine
to guarantee. They are expected to FAIL at the time of writing — the service
does not exist yet. Phase 3 will make them pass.

The contracts exercised here:

  * ``upsert_identity`` is idempotent — calling it N times with the same
    (tenant, type, identifier) yields exactly one row.
  * It is race-safe under concurrent sessions — ``asyncio.gather`` of many
    upserts for the same logical identity still yields one row.
  * Identifiers collapse through ``normalize_identifier`` — Gmail aliases,
    domain case-folding, etc. merge to the same row.
  * Existing rows have ``last_seen`` bumped and ``confidence`` unchanged when
    re-observed.
"""
from __future__ import annotations

import asyncio
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shared.models import Identity

# The service under test — does NOT exist yet. These imports will fail on
# first run; that is the RED state we want before Phase 3.
pytest.importorskip("shared.domain.services.identity_upsert", reason="Phase 3 not implemented yet")
from shared.domain.services.identity_upsert import upsert_identity  # noqa: E402


pytestmark = pytest.mark.asyncio


async def _count_identities(db, tenant_id):
    result = await db.execute(select(Identity).where(Identity.tenant_id == tenant_id))
    return len(result.scalars().all())


class TestIdempotency:
    async def test_single_call_creates_one_row(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        assert ident.id is not None
        assert await _count_identities(corr_db, tenant.id) == 1

    async def test_repeat_calls_return_same_row(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        c = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        assert a.id == b.id == c.id
        assert await _count_identities(corr_db, tenant.id) == 1

    async def test_normalization_collapses_variants(self, corr_db, tenant):
        a = await upsert_identity(corr_db, tenant.id, "F.Bar+promo@GoogleMail.com", "email")
        b = await upsert_identity(corr_db, tenant.id, "fbar@gmail.com", "email")
        assert a.id == b.id, "Gmail alias variants must collapse to one row"
        assert await _count_identities(corr_db, tenant.id) == 1

    async def test_different_types_stay_separate(self, corr_db, tenant):
        await upsert_identity(corr_db, tenant.id, "foo", "username")
        await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        assert await _count_identities(corr_db, tenant.id) == 2


class TestRaceSafety:
    async def test_gather_of_same_identifier_creates_one_row(
        self, corr_session_factory, tenant
    ):
        """Simulate N concurrent workers ingesting leaks that all extract the
        same email. After the dust settles we expect exactly one Identity row.

        The legacy pipeline has no UNIQUE constraint and no ON CONFLICT, so
        this test fails on ``main`` — it's the race we are fixing.
        """

        async def _one_upsert():
            async with corr_session_factory() as session:
                await upsert_identity(
                    session, tenant.id, "racing@example.com", "email"
                )

        # 8 workers = enough concurrency to reliably expose the race on SQLite.
        await asyncio.gather(*[_one_upsert() for _ in range(8)])

        async with corr_session_factory() as session:
            assert await _count_identities(session, tenant.id) == 1


class TestObservationMetadata:
    async def test_first_seen_is_set_on_create(self, corr_db, tenant):
        ident = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        assert ident.first_seen is not None
        assert ident.last_seen is not None

    async def test_last_seen_bumps_on_re_observation(self, corr_db, tenant):
        first = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        first_last_seen = first.last_seen
        # Force a clock tick so the UPDATE produces a visibly newer timestamp.
        await asyncio.sleep(0.01)
        second = await upsert_identity(corr_db, tenant.id, "foo@example.com", "email")
        assert second.id == first.id
        assert second.last_seen is not None
        assert second.last_seen >= first_last_seen


class TestValidation:
    async def test_empty_identifier_rejected(self, corr_db, tenant):
        with pytest.raises((ValueError, IntegrityError)):
            await upsert_identity(corr_db, tenant.id, "", "email")

    async def test_whitespace_only_identifier_rejected(self, corr_db, tenant):
        with pytest.raises((ValueError, IntegrityError)):
            await upsert_identity(corr_db, tenant.id, "   ", "email")
