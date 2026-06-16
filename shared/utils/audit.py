"""Legacy audit entrypoint — thin wrapper around the hash-chained writer.

Historically this module contained the ``AuditLogger.log`` coroutine that
simply ``db.add``-ed a raw ``AuditLog`` row and ``flush``-ed it. That left
every audit entry in a state where any operator with DB access could edit
or delete rows and the change would be undetectable.

The correlation-engine rework introduced
:func:`shared.utils.audit_chain.write_audit`, which appends the same row
but computes ``prev_hash`` / ``self_hash`` so the tenant's audit history
becomes tamper-evident. This module now forwards the legacy call into that
writer — with ``flush_only=True`` so existing callers that wrapped
``AuditLogger.log`` inside a larger transaction keep the same atomicity.

Keep using ``AuditLogger.log`` from existing endpoints; migrate to the
direct ``write_audit`` API when touching a file for other reasons.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import AuditLog
from shared.utils.audit_chain import write_audit


class AuditLogger:
    """Chain-integrated audit writer. Every call now produces a row with
    ``prev_hash`` + ``self_hash`` populated; verify the tenant history via
    :func:`shared.utils.audit_chain.verify_chain`.
    """

    @staticmethod
    async def log(
        db: AsyncSession,
        user_id: str,
        tenant_id: str,
        action: str,
        resource_type: str = None,
        resource_id: str = None,
        details: dict = None,
        ip_address: str = None,
    ) -> AuditLog:
        # flush_only=True preserves the legacy contract: many callers rely
        # on the audit write being atomic with a sibling mutation in the
        # same session (e.g. "toggle VIP" + "log the change" in one commit).
        return await write_audit(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            flush_only=True,
        )
