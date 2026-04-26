"""Evidence-gated, idempotent, reversible identity merge engine.

Replaces the legacy username-prefix merger (``identity_merging.py``) that:

  * Merged on string prefix alone ("hacker@gmail.com" + "hacker@attacker.com");
  * Inflated risk scores on every replay;
  * Allowed VIP slaves to be silently demoted under unprotected masters;
  * Had no undo and no audit trail.

The new engine takes *evidence* — a list of signals with independent
strengths — and only proceeds if the aggregate confidence clears a
configurable threshold. Every merge is recorded in the append-only
``merge_events`` table with a SHA-256 hash chain so the full merge history
of a tenant is tamper-evident. Reversal is a soft update (``reversed_at``)
so the ledger stays append-only.

Public surface:
    * :func:`merge_identities` — create or return the active merge event.
    * :func:`reverse_merge` — soft-reverse an event, restoring independence.
    * :func:`aggregate_confidence` — pure helper, useful for previewing a
      proposed merge in the UI without writing.
    * Exceptions re-exported from ``.exceptions`` for caller convenience.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.services.exceptions import (
    CrossTenantMerge,
    InsufficientEvidence,
    VipInvariantViolation,
)
from shared.models import Identity, MergeEvent

# Evidence with aggregate confidence below this value is refused. The
# default is calibrated so that a single weak signal (strength < 0.5) never
# triggers a merge on its own, while two moderate signals (0.4 each) can.
MIN_CONFIDENCE: float = 0.5


# ─── Evidence aggregation ────────────────────────────────────────────────────


def aggregate_confidence(evidence: Iterable[dict] | None) -> float:
    """Fuse independent evidence strengths via ``1 - Π(1 - s_i)``.

    Treats each evidence item as an independent Bernoulli signal that the
    merge is correct. Aggregate confidence is the probability that at least
    one signal is right; individual strengths are clamped to [0, 1] to stay
    within the probability interpretation.
    """
    if not evidence:
        return 0.0
    product = 1.0
    for item in evidence:
        try:
            s = float(item.get("strength", 0.0))
        except (TypeError, ValueError):
            s = 0.0
        if s < 0.0:
            s = 0.0
        elif s > 1.0:
            s = 1.0
        product *= 1.0 - s
    return 1.0 - product


# ─── Hash-chain helpers ──────────────────────────────────────────────────────


def _canonical_payload(
    *,
    prev_hash: str | None,
    tenant_id: str,
    master_id: str,
    slave_id: str,
    evidence: list[dict],
    confidence: float,
    performed_by: str | None,
    performed_at: datetime,
) -> str:
    # sort_keys guarantees identical byte sequences across interpreters and
    # across rehashes; separators drop whitespace that is not part of the
    # canonical form. Confidence is rounded to 6 dp so minute floating-point
    # drift does not invalidate a chain across processes.
    return json.dumps(
        {
            "prev_hash": prev_hash,
            "tenant_id": tenant_id,
            "master_id": master_id,
            "slave_id": slave_id,
            "evidence": evidence,
            "confidence": round(float(confidence), 6),
            "performed_by": performed_by,
            "performed_at": performed_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,  # e.g. UUID instances
    )


def _sha256_hex(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


async def _acquire_tenant_chain_lock(db: AsyncSession, tenant_id: str) -> None:
    """On Postgres, serialize concurrent chain appends per tenant.

    SQLite is a single-writer engine so append order is already total; the
    advisory lock is a Postgres-only safeguard against two masters reading
    the same chain head and producing a fork. The lock is transaction-scoped
    and released on commit/rollback.
    """
    if db.bind is None:
        return
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        # hashtext is stable + cheap; scoping the advisory lock to tenant_id
        # means other tenants can still append concurrently.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:tid))"),
            {"tid": tenant_id},
        )


# ─── Public merge / reverse ──────────────────────────────────────────────────


async def merge_identities(
    db: AsyncSession,
    *,
    master: Identity,
    slave: Identity,
    evidence: list[dict[str, Any]],
    performed_by: str | None = None,
) -> MergeEvent:
    """Merge *slave* under *master*, recording an append-only ``MergeEvent``.

    Semantics:
      * Idempotent — calling again with the same (master, slave) pair
        returns the existing active event; nothing is re-written.
      * Evidence-gated — aggregate confidence must reach ``MIN_CONFIDENCE``.
      * VIP-preserving — if the slave is protected and the master is not,
        the master is promoted (with that promotion recorded in the
        evidence trail) rather than silently demoting the slave.
      * Tenant-isolated — merges across tenants raise.
      * Hash-chained — ``prev_hash`` references the previous merge event's
        ``self_hash`` in the same tenant; ``self_hash`` is a SHA-256 over
        the canonical payload.

    The risk score of the master is **not** recomputed here — it is flipped
    to dirty and picked up by the lazy recompute worker in Phase 4.
    """
    if master.id == slave.id:
        raise ValueError("cannot merge an identity with itself")

    if master.tenant_id != slave.tenant_id:
        raise CrossTenantMerge(f"master tenant {master.tenant_id} != slave tenant {slave.tenant_id}")

    conf = aggregate_confidence(evidence)
    if conf < MIN_CONFIDENCE:
        raise InsufficientEvidence(f"aggregate confidence {conf:.3f} below threshold {MIN_CONFIDENCE}")

    # Idempotency — if an active merge for this pair already exists, return
    # it unchanged. Checked BEFORE acquiring the chain lock so repeat calls
    # are a fast read on the busy path.
    existing_stmt = select(MergeEvent).where(
        MergeEvent.tenant_id == master.tenant_id,
        MergeEvent.master_id == master.id,
        MergeEvent.slave_id == slave.id,
        MergeEvent.reversed_at.is_(None),
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    # VIP invariant. Policy: promote the master rather than refuse — the
    # operator's intent to merge is honoured while no protection is lost.
    # Sites that want a stricter policy can subclass and raise
    # :class:`VipInvariantViolation` instead.
    promoted = False
    if slave.is_protected and not master.is_protected:
        master.is_protected = True
        promoted = True

    enriched_evidence = list(evidence)
    if promoted:
        enriched_evidence.append({"type": "vip_promotion", "detail": "master promoted to protected"})

    # Serialize chain appends for this tenant, then fetch the current head.
    await _acquire_tenant_chain_lock(db, master.tenant_id)
    head_stmt = (
        select(MergeEvent.self_hash)
        .where(MergeEvent.tenant_id == master.tenant_id)
        .order_by(MergeEvent.performed_at.desc(), MergeEvent.id.desc())
        .limit(1)
    )
    prev_hash = (await db.execute(head_stmt)).scalar_one_or_none()

    # Naive UTC for consistent round-tripping across SQLite (text storage
    # with no tz) and Postgres. See identity_upsert for the same rationale.
    performed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    event_id = str(uuid.uuid4())
    self_hash = _sha256_hex(
        _canonical_payload(
            prev_hash=prev_hash,
            tenant_id=master.tenant_id,
            master_id=master.id,
            slave_id=slave.id,
            evidence=enriched_evidence,
            confidence=conf,
            performed_by=performed_by,
            performed_at=performed_at,
        )
    )

    event = MergeEvent(
        id=event_id,
        tenant_id=master.tenant_id,
        master_id=master.id,
        slave_id=slave.id,
        evidence=enriched_evidence,
        confidence=conf,
        performed_by=performed_by,
        performed_at=performed_at,
        prev_hash=prev_hash,
        self_hash=self_hash,
    )
    db.add(event)

    # Subordinate the slave and dirty the master's risk score. Dirty is a
    # hint to the lazy recompute worker (Phase 4) — we deliberately do not
    # compute here so merge latency stays predictable and replays cheap.
    slave.master_identity_id = master.id
    master.risk_score_dirty = True

    await db.commit()
    await db.refresh(event)
    return event


async def reverse_merge(
    db: AsyncSession,
    event: MergeEvent,
    *,
    reason: str,
    reversed_by: str | None = None,
) -> MergeEvent:
    """Soft-reverse *event*. The row stays in the ledger with ``reversed_at``
    set; the slave regains its independent master_identity_id, and both
    master + slave are flipped to risk-dirty.

    Idempotent: reversing an already-reversed event is a no-op.
    """
    if event.reversed_at is not None:
        return event

    slave = await db.get(Identity, event.slave_id)
    if slave is not None:
        slave.master_identity_id = None
        slave.risk_score_dirty = True

    master = await db.get(Identity, event.master_id)
    if master is not None:
        master.risk_score_dirty = True

    event.reversed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    event.reversed_by = reversed_by
    event.reverse_reason = reason

    await db.commit()
    await db.refresh(event)
    return event


__all__ = [
    "merge_identities",
    "reverse_merge",
    "aggregate_confidence",
    "MIN_CONFIDENCE",
    # Re-exported for caller convenience — ``from entity_resolution import *``
    # should give you everything needed to handle failure modes.
    "InsufficientEvidence",
    "CrossTenantMerge",
    "VipInvariantViolation",
]
