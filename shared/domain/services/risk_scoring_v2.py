"""Lazy, merge-aware risk scoring.

Replaces the legacy ``risk_scoring.py`` which recomputed scores eagerly in
the correlation hot path and left master rows stale after merges. The v2
model splits the concern into three pure-function-friendly parts:

    * :func:`compute_risk_for_identity` — pure read. Walks the merge
      cluster (self + all descendants via ``master_identity_id``), gathers
      linked leak severities, returns an integer in [0, 100]. Never writes.
      Used by previews, ad-hoc queries, and the recompute loop below.

    * :func:`mark_dirty` — cheap, write-side flip of ``risk_score_dirty``
      for a set of identity ids. Called by every mutation path that could
      have affected risk: leak ingestion link, merge, reverse_merge.

    * :func:`recompute_dirty` — drains dirty identities for a tenant,
      writes fresh ``risk_score`` values, clears the flag. Safe to run
      from a worker on a schedule; idempotent; concurrency-tolerant because
      we process one row at a time and the final UPDATE carries the flag
      clear.

The scoring formula preserves the legacy semantics so existing analysts
see consistent numbers — average severity (weight 0.6) plus a logarithmic
frequency bonus capped at 100. The difference is *what rows participate*:
a master's score now reflects every leak reachable through its merge
cluster, not just the ones it was directly linked to.
"""
from __future__ import annotations

import math
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Identity, LeakHit, identity_leaks

# Formula weights — preserved from the v1 service so that migration does
# not produce a surprising numeric jump for existing tenants.
_SEVERITY_WEIGHT = 0.6
_FREQUENCY_WEIGHT = 15.0


# ─── Pure scoring helper ─────────────────────────────────────────────────────

def _score_from_severities(severities: list[int]) -> int:
    """Deterministic formula; 0 severities → 0 score."""
    if not severities:
        return 0
    avg = sum(severities) / len(severities)
    # log2(n+1) is bounded above by ~log2(1e9) ≈ 30 for tenant-scale counts;
    # with weight 15 that caps the bonus around 450, but the outer clamp to
    # 100 is what actually decides the ceiling.
    bonus = math.log2(len(severities) + 1) * _FREQUENCY_WEIGHT
    return max(0, min(100, round(avg * _SEVERITY_WEIGHT + bonus)))


# ─── Merge cluster traversal ─────────────────────────────────────────────────

async def _gather_merged_cluster(db: AsyncSession, root_id: str) -> set[str]:
    """Return ``{root_id}`` ∪ every descendant linked via
    ``Identity.master_identity_id``.

    Implemented as a BFS over direct-child queries so we never traverse an
    already-seen id twice; cycles (should they ever arise from a bad merge
    graph) terminate because ``new = set(rows) - cluster`` subtracts the
    visited set on each wave.
    """
    cluster: set[str] = {root_id}
    frontier: set[str] = {root_id}
    while frontier:
        stmt = select(Identity.id).where(
            Identity.master_identity_id.in_(list(frontier))
        )
        children = set((await db.execute(stmt)).scalars().all())
        new = children - cluster
        if not new:
            break
        cluster |= new
        frontier = new
    return cluster


# ─── Public API ──────────────────────────────────────────────────────────────

async def compute_risk_for_identity(db: AsyncSession, identity_id: str) -> int:
    """Compute the risk score for *identity_id* without persisting it.

    Traverses the merge cluster rooted at *identity_id*, aggregates the
    severities of every leak linked to any cluster member via the
    ``identity_leaks`` join table, and applies the v2 formula.

    Returns an integer in [0, 100]. Does NOT read or write
    ``risk_score`` / ``risk_score_dirty`` on any row.
    """
    cluster = await _gather_merged_cluster(db, identity_id)
    if not cluster:
        return 0

    stmt = (
        select(LeakHit.severity_score)
        .join(identity_leaks, identity_leaks.c.leak_id == LeakHit.id)
        .where(identity_leaks.c.identity_id.in_(list(cluster)))
    )
    severities = [s or 0 for s in (await db.execute(stmt)).scalars().all()]
    return _score_from_severities(severities)


async def mark_dirty(db: AsyncSession, identity_ids: Iterable[str]) -> int:
    """Flip ``risk_score_dirty = True`` for each id in *identity_ids*.

    Returns the count of rows touched. A no-op on an empty iterable; callers
    can pass query results directly without worrying about the empty case.
    """
    ids = [i for i in identity_ids if i]
    if not ids:
        return 0
    result = await db.execute(
        update(Identity)
        .where(Identity.id.in_(ids))
        .values(risk_score_dirty=True)
    )
    await db.commit()
    # rowcount is a best-effort hint — SQLite returns the matched-rows count,
    # Postgres returns updated-rows. For our purposes (telemetry, debug log)
    # either is useful; tests do not depend on the exact value.
    return result.rowcount or 0


async def recompute_dirty(db: AsyncSession, tenant_id: str, *, limit: int | None = None) -> int:
    """Drain the dirty set for *tenant_id*: recompute ``risk_score`` and
    clear ``risk_score_dirty`` for every row flagged.

    :param limit: cap on rows processed per invocation, so a worker can
        bound its tick cost. ``None`` means drain fully.
    :returns: number of identities recomputed.
    """
    stmt = (
        select(Identity.id)
        .where(
            Identity.tenant_id == tenant_id,
            Identity.risk_score_dirty.is_(True),
        )
        .order_by(Identity.id)  # deterministic drain order for reproducibility
    )
    if limit is not None:
        stmt = stmt.limit(int(limit))

    dirty_ids = (await db.execute(stmt)).scalars().all()
    if not dirty_ids:
        return 0

    # Compute every score BEFORE writing any of them. This way the cluster
    # walk for each row sees the full pre-drain merge graph, which matters
    # only subtly (a concurrent reverse_merge during drain could race), but
    # is the conservative default. The writes are then a single UPDATE per
    # row; we batch them under one commit.
    scores: dict[str, int] = {}
    for ident_id in dirty_ids:
        scores[ident_id] = await compute_risk_for_identity(db, ident_id)

    for ident_id, score in scores.items():
        await db.execute(
            update(Identity)
            .where(Identity.id == ident_id)
            .values(risk_score=score, risk_score_dirty=False)
        )

    await db.commit()
    return len(dirty_ids)


__all__ = [
    "compute_risk_for_identity",
    "mark_dirty",
    "recompute_dirty",
]
