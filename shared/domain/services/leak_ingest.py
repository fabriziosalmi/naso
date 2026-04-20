"""Ingest a leak with fuzzy deduplication.

The legacy pipeline deduplicates leaks by SHA-256 of the raw content. That
catches byte-identical payloads but misses the realistic scenario of the
*same leak arriving twice with slightly different formatting* — a Telegram
forward vs. the origin, a Pastebin raw vs. its HTML wrapper, encoding
differences, extra whitespace. Every such variant currently becomes a
separate LeakHit row, polluting the correlation graph and inflating counts.

This service adds a near-duplicate layer on top of exact dedup:

    1. Normalize the content via ``normalize_content`` (NFKC + lowercase +
       whitespace collapse, preserving identifier-structural punctuation).
    2. Fingerprint it with 64-bit SimHash over word trigrams.
    3. Look for a tenant-scoped existing row within Hamming distance ≤ 3
       of the fingerprint. If found, that's the canonical leak; bump its
       ``severity_score`` if the new observation scores higher (never
       downgrade) and return the existing row.
    4. Otherwise, insert a fresh row with normalization + fingerprint
       populated.

Tenant isolation is enforced by the lookup ``WHERE tenant_id = ...`` clause
— two tenants can legitimately hold the same content.

The Hamming threshold (3) is the canonical SimHash near-duplicate cutoff
for short-to-medium text. Increase it to widen the dedup net (more false
positives); decrease it for strict matching (more duplicates slip through).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.normalization import (
    hamming_distance,
    normalize_content,
    simhash64,
)
from shared.models import LeakHit

# Hamming distance at or below this is considered a near-duplicate.
NEAR_DUP_THRESHOLD: int = 3

# Truncate stored snippet to keep indexable rows small. The full content
# lives in MinIO via ``raw_data_url`` for forensic retrieval.
_SNIPPET_LIMIT: int = 500


async def _find_near_duplicate(
    db: AsyncSession, tenant_id: str, fingerprint: int
) -> LeakHit | None:
    """Return the first tenant leak within ``NEAR_DUP_THRESHOLD`` Hamming
    distance of *fingerprint*, or ``None``.

    Current implementation is an in-Python scan over rows with a non-null
    fingerprint for the tenant. For the expected scale of a single tenant
    (thousands, not millions, of active leaks) this is O(n) and fast
    enough. A future upgrade can bucket the fingerprint into four 16-bit
    prefixes and query an LSH-style index — the SQL change is isolated to
    this helper and does not propagate to callers.
    """
    stmt = select(LeakHit).where(
        LeakHit.tenant_id == tenant_id,
        LeakHit.simhash64.is_not(None),
    )
    candidates = (await db.execute(stmt)).scalars().all()
    for cand in candidates:
        if hamming_distance(cand.simhash64, fingerprint) <= NEAR_DUP_THRESHOLD:
            return cand
    return None


async def ingest_leak(
    db: AsyncSession,
    *,
    tenant_id: str,
    source: str,
    content: str,
    severity_score: int = 0,
    status: str = "new",
    raw_data_url: str | None = None,
    metadata_json: dict[str, Any] | None = None,
    screenshot_path: str | None = None,
) -> LeakHit:
    """Return the canonical ``LeakHit`` for *content* in *tenant_id*.

    Creates a new row on a cache miss or returns the existing near-duplicate
    (with ``severity_score`` bumped if the new observation is more severe).
    The returned ORM instance is attached to *db* and has every persisted
    field populated (including the freshly-written normalization +
    fingerprint).
    """
    if tenant_id is None or not str(tenant_id).strip():
        raise ValueError("tenant_id is required")
    if source is None or not str(source).strip():
        raise ValueError("source is required")
    if content is None:
        raise ValueError("content cannot be None")

    normalized = normalize_content(content)
    fingerprint = simhash64(normalized)

    # ── Near-duplicate short-circuit ─────────────────────────────────────
    existing = await _find_near_duplicate(db, tenant_id, fingerprint)
    if existing is not None:
        # Severity monotonically rises — we never downgrade a leak based on
        # a subsequent, weaker observation. This matches the operator mental
        # model: evidence accumulates, it doesn't unravel.
        if severity_score > (existing.severity_score or 0):
            await db.execute(
                update(LeakHit)
                .where(LeakHit.id == existing.id)
                .values(severity_score=severity_score)
            )
            await db.commit()
            await db.refresh(existing)
        return existing

    # ── New row ──────────────────────────────────────────────────────────
    snippet = content[:_SNIPPET_LIMIT] if isinstance(content, str) else None
    leak = LeakHit(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        source=source,
        content_snippet=snippet,
        raw_data_url=raw_data_url,
        metadata_json=metadata_json,
        severity_score=max(0, min(100, int(severity_score or 0))),
        status=status,
        screenshot_path=screenshot_path,
        normalized_content=normalized,
        simhash64=fingerprint,
    )
    db.add(leak)
    await db.commit()
    await db.refresh(leak)
    return leak


__all__ = ["ingest_leak", "NEAR_DUP_THRESHOLD"]
