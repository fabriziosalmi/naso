"""Identity correlation (Command Side).

Previous revision created ``Identity`` rows via raw ``Identity(...)`` constructors
and recomputed risk eagerly per identity. That pattern had three serious flaws:

    1. **Race condition** — no UNIQUE constraint and no ON CONFLICT handling
       meant two concurrent workers extracting the same email both succeeded
       with ``INSERT``, producing duplicate ``Identity`` rows.
    2. **Eager recompute** — ``IdentityRiskScoringService.calculate_and_update_risk``
       was called once per new identity inside the hot path, stacking N SQL
       round trips before the correlation transaction could commit.
    3. **Stale master scores** — risk for masters higher up the merge tree
       was never invalidated, so identifiers surfaced under a master had no
       effect on its risk until the next manual recompute.

This revision keeps the public ``IdentityCorrelationService.correlate_leak``
signature so :mod:`shared.tasks.pipeline` does not need to change, but
replaces the internals with:

    * :func:`shared.domain.services.identity_upsert.upsert_identity` — one
      call per extracted email, idempotent under concurrency.
    * A dialect-aware ``INSERT ... ON CONFLICT DO NOTHING`` on the
      ``identity_leaks`` join table so duplicate link attempts are no-ops
      rather than ``IntegrityError`` cascades.
    * :func:`shared.domain.services.risk_scoring_v2.mark_dirty` — a single
      batch-flip of ``risk_score_dirty`` for all touched identities. The
      periodic ``recompute_dirty`` worker then produces fresh scores off
      the hot path, and masters up the merge tree are included automatically
      because the traversal walks the cluster.

The notification + MITRE + webhook flow is unchanged; analysts observe the
same downstream behaviour.
"""
import logging
import os
import re
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import Identity, User, identity_leaks
from .identity_upsert import upsert_identity
from .mitre import MitreMappingService
from .risk_scoring_v2 import mark_dirty
from .webhooks import WebhookService

logger = logging.getLogger("naso-correlation")

# P-14: read once at import time — not on every hot-path call via os.getenv().
_CRITICAL_THRESHOLD: int = int(os.getenv("CRITICAL_SCORE_THRESHOLD", "80"))


def _dialect_insert(db: AsyncSession):
    """Dialect-specific ``insert`` so we can call ``on_conflict_do_nothing()``
    against the ``identity_leaks`` join table portably."""
    name = db.bind.dialect.name if db.bind is not None else ""
    if name == "postgresql":
        return pg_insert
    if name == "sqlite":
        return sqlite_insert
    raise RuntimeError(f"unsupported dialect for leak link: {name!r}")


async def _link_identities_to_leak(
    db: AsyncSession, leak_id: str, identity_ids: Iterable[str]
) -> None:
    """Idempotently link every identity in *identity_ids* to *leak_id*.

    The join table has a composite PK ``(identity_id, leak_id)``; a duplicate
    link would normally raise ``IntegrityError``. Using the dialect's
    ``on_conflict_do_nothing`` collapses the retry path into a single
    statement per link and keeps the session transaction usable after the
    call (a naked INSERT + catch would poison it).
    """
    ins = _dialect_insert(db)
    for ident_id in identity_ids:
        stmt = ins(identity_leaks).values(
            identity_id=ident_id, leak_id=leak_id
        ).on_conflict_do_nothing()
        await db.execute(stmt)


class IdentityCorrelationService:
    """Command-side correlation facade. The signature is preserved for
    compatibility with :mod:`shared.tasks.pipeline`; the implementation now
    delegates to the v2 services introduced by the correlation-engine
    rework.
    """

    # Kept for compatibility with any caller importing the class attribute.
    EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    @classmethod
    async def correlate_leak(
        cls,
        db: AsyncSession,
        leak_id: str,
        content: str,
        tenant_id: str,
        screenshot_path: str = None,
        preextracted_emails: set = None,  # P-08: reuse Babel output, skip duplicate regex scan
        severity_score: int = None,        # P-13: avoid DB re-query for leak severity
        leak_source: str = None,           # P-13: avoid DB re-query for leak source
    ):
        # 1. Extract emails — use Babel output when present (P-08).
        emails = preextracted_emails if preextracted_emails else set(re.findall(cls.EMAIL_REGEX, content))
        if not emails:
            await MitreMappingService.map_leak_to_ttp(db, leak_id, content)
            await db.commit()
            return

        # 2. Upsert each identity. upsert_identity is idempotent + race-safe;
        # it commits internally per call, which matches the legacy behaviour
        # where each new identity was persisted before link creation.
        identities: list[Identity] = []
        for email in emails:
            try:
                ident = await upsert_identity(db, tenant_id, email, "email")
            except ValueError:
                # Empty / malformed identifier — skip, don't abort the whole leak.
                continue
            identities.append(ident)

        if not identities:
            await MitreMappingService.map_leak_to_ttp(db, leak_id, content)
            await db.commit()
            return

        # 3. Link each identity to the leak (idempotent via ON CONFLICT).
        await _link_identities_to_leak(db, leak_id, [i.id for i in identities])

        # 4. Dirty the touched identities so the lazy recompute worker picks
        # them up. Walking up the merge tree is handled inside
        # compute_risk_for_identity at recompute time — we only mark leaves
        # here. If an identity is already a slave, its master will be
        # surfaced via the cluster traversal when the worker runs.
        await mark_dirty(db, [i.id for i in identities])

        # 5. MITRE mapping (unchanged).
        await MitreMappingService.map_leak_to_ttp(db, leak_id, content)
        await db.commit()

        # 6. Notifications + webhook (unchanged semantics).
        effective_severity = severity_score if severity_score is not None else 0
        effective_source = leak_source or "unknown"
        protected_emails = {i.identifier for i in identities if i.is_protected}

        if effective_severity >= _CRITICAL_THRESHOLD:
            await cls.notify_critical_hits(
                db, tenant_id, effective_source, effective_severity, emails, is_priority=False
            )
            await WebhookService.trigger_critical_leak(
                db, tenant_id, {"id": leak_id, "source": effective_source, "severity": effective_severity}
            )
        elif protected_emails:
            await cls.notify_critical_hits(
                db, tenant_id, effective_source, effective_severity, protected_emails, is_priority=True
            )
            await WebhookService.trigger_critical_leak(
                db, tenant_id, {"id": leak_id, "source": f"[VIP] {effective_source}", "severity": effective_severity}
            )

    @classmethod
    async def notify_critical_hits(
        cls,
        db: AsyncSession,
        tenant_id: str,
        leak_source: str,
        severity: int,
        emails: set,
        is_priority: bool = False,
    ):
        """One digest per admin, not N×M email for (identity × admin) (P-11)."""
        user_result = await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "admin"))
        admins = user_result.scalars().all()
        if not admins:
            return

        from ...utils.notifications import NotificationService

        summary = list(emails)[0] if len(emails) == 1 else f"{len(emails)} identities compromised"
        for admin in admins:
            NotificationService.send_breach_alert(
                recipient_email=admin.email,
                identity_identifier=summary,
                leak_source=leak_source,
                severity=severity,
                is_priority=is_priority,
            )
