"""Proposes identity merges based on shared-leak evidence.

Replaces the legacy ``IdentityMergingService.auto_merge_identities`` which
merged any two identities whose identifier-before-``@`` matched — a rule
that catastrophically conflates people ("hacker@gmail.com" +
"hacker@attacker.com" → same master). That heuristic is gone; merges now
require *actual* evidence, and the strongest evidence available to us is
two identities appearing together in the same leak.

Pipeline:

    1. For the given tenant, find every pair of active (non-slave,
       non-self) identities that share at least one ``LeakHit`` via the
       ``identity_leaks`` join table.
    2. For each pair, build an evidence list — one entry per shared leak,
       strength calibrated so a single leak clears the merge threshold.
    3. Call :func:`merge_identities` for each pair; skip pairs whose
       evidence does not pass the confidence gate (``InsufficientEvidence``
       is raised and caught so a weak pair does not abort the batch).

The master of a pair is the identity with the higher ``risk_score`` —
tie-broken by earliest ``first_seen`` so the more-established record wins.
VIP-preserving promotion is handled inside ``merge_identities`` itself.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.services.entity_resolution import merge_identities
from shared.domain.services.exceptions import (
    CrossTenantMerge,
    InsufficientEvidence,
    VipInvariantViolation,
)
from shared.models import Identity, identity_leaks

# Strength per shared-leak evidence item. With the default
# ``MIN_CONFIDENCE = 0.5`` in entity_resolution, a single shared leak
# (aggregate = 0.7) already clears the gate — which matches the operator
# intuition that one unambiguous co-occurrence is strong evidence.
SHARED_LEAK_STRENGTH = 0.7


async def gather_shared_leak_pairs(
    db: AsyncSession, tenant_id: str
) -> dict[tuple[str, str], list[str]]:
    """Return a ``{(id_a, id_b): [shared_leak_id, ...]}`` map for every
    ordered pair of currently-active (master-level) identities in this
    tenant that share at least one leak.

    The pair key is sorted so ``(a, b)`` and ``(b, a)`` collapse into one
    entry — the master/slave choice is made separately once we have the
    evidence set.
    """
    stmt = (
        select(
            identity_leaks.c.identity_id,
            identity_leaks.c.leak_id,
        )
        .join(Identity, Identity.id == identity_leaks.c.identity_id)
        .where(
            Identity.tenant_id == tenant_id,
            Identity.master_identity_id.is_(None),  # only masters participate
        )
    )
    rows = (await db.execute(stmt)).all()

    # leak_id → [identity_id, ...]
    by_leak: dict[str, list[str]] = {}
    for ident_id, leak_id in rows:
        by_leak.setdefault(leak_id, []).append(ident_id)

    pairs: dict[tuple[str, str], list[str]] = {}
    for leak_id, ident_ids in by_leak.items():
        if len(ident_ids) < 2:
            continue
        # Deduplicate and sort so each unordered pair has a canonical key.
        unique = sorted(set(ident_ids))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                pairs.setdefault((unique[i], unique[j]), []).append(leak_id)
    return pairs


def choose_master(a: Identity, b: Identity) -> tuple[Identity, Identity]:
    """Return ``(master, slave)``. Higher risk wins; tie-break by earliest
    ``first_seen``; last resort: lexicographic id (stable, deterministic).
    """
    risk_a = a.risk_score or 0
    risk_b = b.risk_score or 0
    if risk_a != risk_b:
        return (a, b) if risk_a > risk_b else (b, a)

    fs_a, fs_b = a.first_seen, b.first_seen
    if fs_a is not None and fs_b is not None and fs_a != fs_b:
        return (a, b) if fs_a < fs_b else (b, a)

    return (a, b) if a.id < b.id else (b, a)


async def propose_and_merge(
    db: AsyncSession,
    tenant_id: str,
    *,
    performed_by: str | None = None,
) -> dict:
    """Scan the tenant for merge-worthy pairs and execute every pair that
    clears the confidence threshold.

    Returns a report dict with counts and the list of successfully merged
    pairs. Pairs that fail the VIP invariant (which is policy-enforced to
    *promote* by default) or the confidence gate are reported but not
    merged.
    """
    pair_to_leaks = await gather_shared_leak_pairs(db, tenant_id)
    if not pair_to_leaks:
        return {"merged_count": 0, "skipped_weak": 0, "skipped_invariant": 0, "pairs": []}

    merged: list[dict] = []
    skipped_weak = 0
    skipped_invariant = 0

    for (id_a, id_b), shared_leaks in pair_to_leaks.items():
        a = await db.get(Identity, id_a)
        b = await db.get(Identity, id_b)
        if a is None or b is None:
            continue
        # Guard: if either side is no longer an active master (a concurrent
        # merge subordinated it in the same loop), skip silently.
        if a.master_identity_id is not None or b.master_identity_id is not None:
            continue

        master, slave = choose_master(a, b)
        evidence = [
            {"type": "shared_leak", "leak_id": lid, "strength": SHARED_LEAK_STRENGTH}
            for lid in shared_leaks
        ]
        try:
            event = await merge_identities(
                db,
                master=master,
                slave=slave,
                evidence=evidence,
                performed_by=performed_by,
            )
        except InsufficientEvidence:
            skipped_weak += 1
            continue
        except VipInvariantViolation:
            skipped_invariant += 1
            continue
        except CrossTenantMerge:
            # Shouldn't happen given the tenant filter above, but guard
            # against FK inconsistency defensively.
            continue

        merged.append(
            {
                "event_id": event.id,
                "master_id": master.id,
                "slave_id": slave.id,
                "confidence": event.confidence,
                "shared_leak_count": len(shared_leaks),
            }
        )

    return {
        "merged_count": len(merged),
        "skipped_weak": skipped_weak,
        "skipped_invariant": skipped_invariant,
        "pairs": merged,
    }


__all__ = [
    "propose_and_merge",
    "gather_shared_leak_pairs",
    "choose_master",
    "SHARED_LEAK_STRENGTH",
]
