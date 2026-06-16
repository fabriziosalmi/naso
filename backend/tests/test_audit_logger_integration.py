"""Integration: the legacy ``AuditLogger.log`` entrypoint now produces
hash-chained rows via the new writer. Every existing endpoint that calls
``AuditLogger.log`` gains tamper-evidence for free.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from shared.models import AuditLog
from shared.utils.audit import AuditLogger
from shared.utils.audit_chain import verify_chain

pytestmark = pytest.mark.asyncio


class TestLegacyEntrypointChains:
    async def test_single_log_is_chained(self, corr_db, tenant, user):
        row = await AuditLogger.log(
            corr_db,
            user_id=user.id,
            tenant_id=tenant.id,
            action="CREATE_IDENTITY",
            resource_type="identity",
            resource_id="id-1",
            details={"identifier": "foo@example.com"},
        )
        await corr_db.commit()  # legacy entrypoint flushes, caller commits

        assert row.prev_hash is None
        assert row.self_hash and len(row.self_hash) == 64

    async def test_multiple_logs_link_in_order(self, corr_db, tenant, user):
        await AuditLogger.log(corr_db, user_id=user.id, tenant_id=tenant.id, action="A")
        await AuditLogger.log(corr_db, user_id=user.id, tenant_id=tenant.id, action="B")
        await AuditLogger.log(corr_db, user_id=user.id, tenant_id=tenant.id, action="C")
        await corr_db.commit()

        # Chain verifies end-to-end.
        result = await verify_chain(corr_db, tenant_id=tenant.id)
        assert result.ok is True, result.reason

        rows = (
            (
                await corr_db.execute(
                    select(AuditLog).where(AuditLog.tenant_id == tenant.id).order_by(AuditLog.timestamp, AuditLog.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3
        assert rows[0].prev_hash is None
        assert rows[1].prev_hash == rows[0].self_hash
        assert rows[2].prev_hash == rows[1].self_hash
