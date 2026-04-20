"""Idempotent, race-safe ``upsert_identity``.

The legacy correlation path created ``Identity`` rows via plain ``INSERT``
with no UNIQUE constraint and no conflict handling. Two concurrent leak
pipelines extracting the same email could — and did — produce duplicate
rows. This module replaces that with a deterministic upsert built on top of
the ``(tenant_id, type, normalized_identifier)`` unique constraint added by
migration ``20260420_01_corr_v2``.

Implementation strategy: **dialect-specific ``INSERT ... ON CONFLICT DO
NOTHING``**, not try/except on ``IntegrityError``. Both SQLite and Postgres
support the syntax natively; relying on it avoids the subtle trap where
``AsyncSession.rollback()`` expires every ORM instance in the session,
breaking the race-safety test (sibling objects from earlier calls become
lazy-loaders in an async context, which raises ``MissingGreenlet``).

Contract (full detail in ``backend/tests/test_identity_upsert.py``):

    * Deterministic — same raw identifier, same canonical row. Gmail
      aliases and domain casing collapse via
      :func:`shared.domain.normalization.normalize_identifier`.
    * Idempotent — repeat calls return the same row and bump ``last_seen``.
    * Race-safe — concurrent sessions under ``asyncio.gather`` converge on
      exactly one row, via the UNIQUE constraint and ``ON CONFLICT DO NOTHING``.
    * Validated — empty / whitespace-only identifiers (before OR after
      normalization) raise ``ValueError``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.normalization import normalize_identifier
from shared.models import Identity


def _on_conflict_insert(db: AsyncSession):
    """Return the dialect's ``insert`` construct so we can call
    ``.on_conflict_do_nothing(...)`` portably."""
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "postgresql":
        return pg_insert
    if dialect == "sqlite":
        return sqlite_insert
    raise RuntimeError(f"unsupported dialect for upsert: {dialect!r}")


async def upsert_identity(
    db: AsyncSession,
    tenant_id: str,
    raw_identifier: str,
    type_: str,
    *,
    confidence: float = 1.0,
) -> Identity:
    """Insert the identity row if it does not exist; otherwise return the
    existing row with ``last_seen`` refreshed.

    Always commits before returning. Safe to call from any session that
    uses ``expire_on_commit=False`` (the default everywhere in NASO).
    """
    if raw_identifier is None or not str(raw_identifier).strip():
        raise ValueError("identifier cannot be empty or whitespace")

    normalized = normalize_identifier(raw_identifier, type_)
    if not normalized:
        # After normalization we can still end up empty (e.g. phone with no
        # digits). Refuse at the service boundary — the alternative is a
        # UNIQUE collision on empty string, which is worse.
        raise ValueError(f"identifier {raw_identifier!r} normalizes to empty")

    # Use naive UTC so the value round-trips identically across SQLite (which
    # stores as ISO text without tz) and Postgres (which preserves tz). With
    # a naive value on write, both backends return a naive value on read, and
    # downstream comparisons across objects that stayed in the identity map
    # versus those reloaded from DB stay consistent.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stripped = str(raw_identifier).strip()

    # ── 1. INSERT ... ON CONFLICT DO NOTHING ──────────────────────────────
    # On conflict the row is untouched — first_seen and confidence survive
    # from the original observation, matching the "observation metadata is
    # write-once" contract.
    insert_ctor = _on_conflict_insert(db)
    stmt = insert_ctor(Identity).values(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        identifier=stripped,
        type=type_,
        normalized_identifier=normalized,
        confidence=confidence,
        first_seen=now,
        last_seen=now,
        risk_score=0,
        risk_score_dirty=False,
        is_protected=False,
    ).on_conflict_do_nothing(
        index_elements=["tenant_id", "type", "normalized_identifier"],
    )
    await db.execute(stmt)

    # ── 2. Bump last_seen on the authoritative row ────────────────────────
    # Always UPDATE — on a fresh INSERT it's a no-op touch-up; on a conflict
    # it refreshes the re-observation timestamp that downstream insights
    # (hot streak, stale critical) rely on.
    await db.execute(
        update(Identity)
        .where(
            Identity.tenant_id == tenant_id,
            Identity.type == type_,
            Identity.normalized_identifier == normalized,
        )
        .values(last_seen=now)
    )

    # ── 3. Fetch and return the authoritative row ─────────────────────────
    row = (
        await db.execute(
            select(Identity).where(
                Identity.tenant_id == tenant_id,
                Identity.type == type_,
                Identity.normalized_identifier == normalized,
            )
        )
    ).scalar_one()

    await db.commit()
    return row


__all__ = ["upsert_identity"]
