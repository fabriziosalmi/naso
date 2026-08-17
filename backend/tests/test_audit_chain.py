"""Contract tests for the audit hash-chain.

Every mutation in NASO produces an ``AuditLog`` row. The rewrite makes those
rows tamper-evident: each new row references the previous row's ``self_hash``
in the same tenant, and carries its own SHA-256 computed deterministically
from the canonical payload. Verification walks the chain and recomputes each
hash, flagging any mismatch.

Contracts:

  * ``write_audit`` populates ``prev_hash`` and ``self_hash`` for every row.
  * The first row in a tenant's chain has ``prev_hash == None``.
  * Subsequent rows link: ``row[n].prev_hash == row[n-1].self_hash``.
  * Tenants have independent chains.
  * ``verify_chain`` returns ``ok=True`` on a pristine chain.
  * ``verify_chain`` returns ``ok=False`` with the index of the first break
    when any field of a middle row is tampered with.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from shared.models import AuditLog, Tenant

pytest.importorskip("shared.utils.audit_chain", reason="Phase 6 not implemented yet")
from shared.utils.audit_chain import verify_chain, write_audit  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _fetch_chain(db, tenant_id):
    return (
        (
            await db.execute(
                select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.timestamp, AuditLog.id)
            )
        )
        .scalars()
        .all()
    )


class TestChainConstruction:
    async def test_first_entry_has_null_prev_hash(self, corr_db, tenant, user):
        row = await write_audit(
            corr_db,
            tenant_id=tenant.id,
            user_id=user.id,
            action="CREATE_IDENTITY",
            resource_type="identity",
            resource_id="id-1",
            details={"hello": "world"},
        )
        assert row.prev_hash is None
        assert row.self_hash and len(row.self_hash) == 64  # SHA-256 hex

    async def test_subsequent_entries_link(self, corr_db, tenant, user):
        r1 = await write_audit(
            corr_db,
            tenant_id=tenant.id,
            user_id=user.id,
            action="A",
            resource_type="identity",
            resource_id="1",
            details={},
        )
        r2 = await write_audit(
            corr_db,
            tenant_id=tenant.id,
            user_id=user.id,
            action="B",
            resource_type="identity",
            resource_id="2",
            details={},
        )
        r3 = await write_audit(
            corr_db,
            tenant_id=tenant.id,
            user_id=user.id,
            action="C",
            resource_type="identity",
            resource_id="3",
            details={},
        )
        assert r2.prev_hash == r1.self_hash
        assert r3.prev_hash == r2.self_hash


class TestTenantIsolation:
    async def test_separate_chains_per_tenant(self, corr_db, tenant, user):
        other = Tenant(id=str(_uuid.uuid4()), name=f"other-{_uuid.uuid4().hex[:6]}")
        corr_db.add(other)
        await corr_db.commit()

        r_a = await write_audit(
            corr_db,
            tenant_id=tenant.id,
            user_id=user.id,
            action="A",
            resource_type="x",
            resource_id="1",
            details={},
        )
        r_b = await write_audit(
            corr_db,
            tenant_id=other.id,
            user_id=user.id,
            action="B",
            resource_type="x",
            resource_id="2",
            details={},
        )
        # First entry in the other tenant must NOT reference the first tenant's hash.
        assert r_b.prev_hash is None
        assert r_b.self_hash != r_a.self_hash


class TestVerification:
    async def test_pristine_chain_verifies(self, corr_db, tenant, user):
        for i in range(5):
            await write_audit(
                corr_db,
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"ACT_{i}",
                resource_type="r",
                resource_id=str(i),
                details={"i": i},
            )
        result = await verify_chain(corr_db, tenant_id=tenant.id)
        assert result.ok is True
        assert result.broken_at is None

    async def test_tamper_with_middle_entry_breaks_chain(self, corr_db, tenant, user):
        for i in range(5):
            await write_audit(
                corr_db,
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"ACT_{i}",
                resource_type="r",
                resource_id=str(i),
                details={"i": i},
            )
        chain = await _fetch_chain(corr_db, tenant.id)
        assert len(chain) == 5

        # Tamper: change the details of row 2 without updating its self_hash.
        chain[2].details = {"i": 999, "evil": True}
        await corr_db.commit()

        result = await verify_chain(corr_db, tenant_id=tenant.id)
        assert result.ok is False
        assert result.broken_at == 2

    async def test_removing_an_entry_breaks_chain(self, corr_db, tenant, user):
        for i in range(4):
            await write_audit(
                corr_db,
                tenant_id=tenant.id,
                user_id=user.id,
                action=f"ACT_{i}",
                resource_type="r",
                resource_id=str(i),
                details={"i": i},
            )
        chain = await _fetch_chain(corr_db, tenant.id)
        await corr_db.delete(chain[1])
        await corr_db.commit()

        result = await verify_chain(corr_db, tenant_id=tenant.id)
        assert result.ok is False


class TestConcurrentWrites:
    """Writes happening in parallel sessions must not fork the chain.

    Guarded by the per-tenant ``asyncio.Lock`` in ``audit_chain`` — without
    it, two coroutines could read the same ``prev_hash`` before either
    committed, resulting in two rows sharing the same link target and an
    irrecoverable chain break.
    """

    async def test_parallel_writes_keep_chain_intact(self, corr_session_factory, tenant, user):
        import asyncio as _asyncio

        # One write per task, 8 tasks, each on its own session to simulate
        # the parallel-tool execution path the agent loop will use.
        async def _one(idx: int):
            async with corr_session_factory() as session:
                await write_audit(
                    session,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    action=f"PAR_{idx}",
                    resource_type="r",
                    resource_id=str(idx),
                    details={"i": idx},
                )

        await _asyncio.gather(*(_one(i) for i in range(8)))

        # Verify via a fresh session so we read committed rows only.
        async with corr_session_factory() as verify_session:
            result = await verify_chain(verify_session, tenant_id=tenant.id)
            assert result.ok is True, (
                f"chain broke under concurrent writes: reason={result.reason}, at={result.broken_at}"
            )

            from sqlalchemy import select as _select

            from shared.models import AuditLog

            rows = (
                (await verify_session.execute(_select(AuditLog).where(AuditLog.tenant_id == tenant.id))).scalars().all()
            )
            assert len(rows) == 8


@pytest.mark.asyncio
async def test_rows_written_before_the_chain_are_not_called_tampered(db):
    """Legacy rows are outside the chain, and saying so is the whole point.

    Every deployment that predates the hash chain has audit rows with NULL
    hashes. Recomputing a digest for them and comparing it to NULL fails, and
    the verifier used to report that failure as

        self_hash mismatch (row content tampered)

    — an accusation of evidence tampering, raised against a healthy system, in
    the one feature whose value is that its answer can be trusted. It painted a
    red "Audit chain integrity broken" banner across the whole application.
    """
    tenant = Tenant(id=str(_uuid.uuid4()), name=f"legacy-{_uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()

    for idx in range(3):
        db.add(
            AuditLog(
                id=str(_uuid.uuid4()),
                tenant_id=tenant.id,
                user_id=None,
                action=f"LEGACY_{idx}",
                resource_type="leak",
                resource_id=str(idx),
                details={},
                prev_hash=None,
                self_hash=None,
            )
        )
    await db.commit()

    result = await verify_chain(db, tenant_id=tenant.id)

    assert result.ok is True, f"legacy rows reported as a break: {result.reason}"
    assert result.legacy_unhashed == 3
    assert result.verified == 0
    assert result.reason is None


@pytest.mark.asyncio
async def test_the_chain_continues_over_legacy_rows(db):
    """New writes after legacy rows verify, and the counts stay honest."""
    tenant = Tenant(id=str(_uuid.uuid4()), name=f"mixed-{_uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()

    db.add(
        AuditLog(
            id=str(_uuid.uuid4()),
            tenant_id=tenant.id,
            action="LEGACY_0",
            details={},
            prev_hash=None,
            self_hash=None,
        )
    )
    await db.commit()

    for idx in range(2):
        await write_audit(db, tenant_id=tenant.id, user_id=None, action=f"NEW_{idx}", details={"i": idx})

    result = await verify_chain(db, tenant_id=tenant.id)

    assert result.ok is True, result.reason
    assert result.legacy_unhashed == 1
    assert result.verified == 2


@pytest.mark.asyncio
async def test_an_unhashed_row_inside_the_chain_is_still_a_break(db):
    """Skipping legacy rows must not become a way to launder a deletion.

    A row with no hash *after* the chain has started is not a legacy row: the
    chain was running when it was written. It fails, with a reason that says
    what was actually observed rather than guessing at intent.
    """
    tenant = Tenant(id=str(_uuid.uuid4()), name=f"gap-{_uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()

    await write_audit(db, tenant_id=tenant.id, user_id=None, action="REAL_0", details={})
    # An explicit, later timestamp. The walk orders by (timestamp, id), and two
    # rows written in the same second tie — leaving a random UUID to decide
    # which comes first, which would put this row at the head and make it look
    # like a legacy row.
    db.add(
        AuditLog(
            id=str(_uuid.uuid4()),
            tenant_id=tenant.id,
            action="SNEAKY",
            details={},
            timestamp=datetime.now(timezone.utc) + timedelta(minutes=5),
            prev_hash=None,
            self_hash=None,
        )
    )
    await db.commit()

    result = await verify_chain(db, tenant_id=tenant.id)

    assert result.ok is False
    assert "unhashed row inside the chain" in result.reason
    assert result.legacy_unhashed == 0
