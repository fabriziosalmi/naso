"""Tamper-evident, hash-chained audit writer + verifier.

Legacy ``shared.utils.audit.AuditLogger.log`` appends rows to ``audit_logs``
without any integrity guarantee — any operator with DB access can mutate a
row and nothing betrays the change. This module replaces the legacy writer
with a hash-chained variant:

    * Each new audit row's ``prev_hash`` references the previous row's
      ``self_hash`` in the same tenant (chains are per-tenant so one
      customer's history cannot corrupt another's).
    * ``self_hash`` is a SHA-256 digest over a canonical JSON
      representation of every field the row contains, including
      ``prev_hash``. Tampering with any field — including the hash linkage
      — breaks verification from the tampered row onwards.
    * Writes serialize appends per tenant on Postgres
      (``pg_advisory_xact_lock``) so concurrent writers cannot fork the
      chain. SQLite is single-writer by construction.

Mirrors the chain scheme already in use for ``merge_events`` (Phase 3), so
both ledgers can be audited with the same verification primitive.

Public surface:
    * :func:`write_audit` — append a new entry with auto-computed links.
    * :func:`verify_chain` — walk the chain for a tenant, returning a
      :class:`VerifyResult` that flags the first broken row (or None).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import AuditLog

# ─── In-process per-tenant serialization ─────────────────────────────────────
# The Postgres advisory lock covers the production deployment, but under
# SQLite (used by the test suite and by single-worker dev setups) the hook
# is a no-op. Two coroutines writing audit entries for the same tenant
# concurrently could both read the same chain head, producing a forked
# chain. This guards the read-then-write sequence with a per-tenant
# ``asyncio.Lock`` so the invariant holds regardless of backend.
#
# The map is lazy — lock instances are only created for tenants that
# actually see audit traffic, and they live for the process lifetime (a
# few hundred bytes each, bounded by the tenant count).
_TENANT_LOCKS: dict[str, asyncio.Lock] = {}
_TENANT_LOCKS_GUARD = asyncio.Lock()


async def _tenant_lock(tenant_id: str | None) -> asyncio.Lock:
    """Return the ``asyncio.Lock`` scoped to *tenant_id*, creating it on
    first use. Null tenants get a single shared ``_system`` lock — system
    audit rows (boot events, cross-tenant admin actions) are rare enough
    that serializing them all together is fine.
    """
    key = tenant_id or "_system"
    async with _TENANT_LOCKS_GUARD:
        lock = _TENANT_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _TENANT_LOCKS[key] = lock
    return lock


# ─── Result object ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a chain verification walk.

    :ivar ok: ``True`` iff every row verifies.
    :ivar broken_at: 0-indexed position of the first failing row, or
        ``None`` when the chain is intact.
    :ivar reason: short human-readable reason for the break; ``None`` on
        success.
    """

    ok: bool
    broken_at: int | None = None
    reason: str | None = None
    #: Rows at the head of the log written before the hash chain existed, and
    #: so outside it. Not a fault, and deliberately not repaired — see the
    #: comment in :func:`verify_chain`.
    legacy_unhashed: int = 0
    #: Rows actually covered by the walk.
    verified: int = 0


# ─── Canonical hashing ───────────────────────────────────────────────────────


def _canonical_timestamp(timestamp: datetime | None) -> str | None:
    """A timestamp string that is the same whether the row was just built or
    read back from the database.

    This is the whole integrity of the chain on Postgres. ``write_audit`` hashes
    a *naive* UTC datetime, but the ``audit_logs.timestamp`` column is
    ``DateTime(timezone=True)``, so Postgres returns the same instant as an
    *aware* datetime on the next read. ``isoformat()`` then produces two
    different strings —

        write:  '2026-08-17T21:24:29.994748'          (naive)
        verify: '2026-08-17T21:24:29.994748+00:00'     (aware, from Postgres)

    — and every genuinely hashed row failed verification with
    ``self_hash mismatch (row content tampered)``. The audit chain, which is the
    product's compliance centrepiece, was broken on the production database. It
    was green in CI because the test suite runs on SQLite, which stores the
    naive value and returns it naive, so the two strings matched there and
    nowhere else.

    Normalising to naive UTC before serialising makes the two paths agree: an
    aware value is converted to UTC and stripped of its tzinfo, a naive value is
    assumed to already be UTC (which ``write_audit`` guarantees). Existing rows
    verify correctly after this change, because the stored hash was computed
    over exactly this naive form.
    """
    if timestamp is None:
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return timestamp.isoformat()


def _canonical_payload(
    *,
    prev_hash: str | None,
    tenant_id: str | None,
    user_id: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    details: dict[str, Any] | None,
    timestamp: datetime,
) -> str:
    # sort_keys + compact separators give a byte-stable serialization across
    # interpreter versions. ``default=str`` gracefully handles datetime, UUID
    # and other types that may leak into ``details`` — consistent coercion
    # matters because we will re-hash the same payload during verification.
    return json.dumps(
        {
            "prev_hash": prev_hash,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "timestamp": _canonical_timestamp(timestamp),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256_hex(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


async def _acquire_tenant_lock(db: AsyncSession, tenant_id: str | None) -> None:
    """Postgres-only advisory lock that serializes chain appends for the
    given tenant. SQLite does not need it — the engine serializes writes
    globally — and some null-tenant audit rows (system boot events) can
    skip locking entirely.
    """
    if tenant_id is None or db.bind is None:
        return
    if db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:tid))"),
            {"tid": tenant_id},
        )


# ─── Public API ──────────────────────────────────────────────────────────────


async def write_audit(
    db: AsyncSession,
    *,
    tenant_id: str | None,
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    flush_only: bool = False,
) -> AuditLog:
    """Append a new audit row with ``prev_hash`` and ``self_hash`` set.

    Chains are **per-tenant**: the ``prev_hash`` lookup is scoped to
    ``tenant_id``, so the first row in a tenant's history has
    ``prev_hash = None`` regardless of what other tenants have written.

    :param flush_only: when ``True``, flush instead of commit so the caller
        can atomically wrap the audit write inside a larger transaction
        (e.g. "update leak status AND audit the change" in one rollback
        scope). The hash chain still reads consistently within the session
        because SQLAlchemy flushes make pending rows visible to subsequent
        queries in the same session. Default ``False`` commits, which is
        what one-shot audit writes want.
    """
    # Serialize the read-then-write sequence against any other coroutine
    # appending to the same tenant's chain. Under SQLite this is the only
    # mechanism preventing a fork; under Postgres the advisory_xact_lock
    # below handles cross-process serialization as well, so having both
    # is belt-and-braces.
    lock = await _tenant_lock(tenant_id)
    async with lock:
        await _acquire_tenant_lock(db, tenant_id)

        # Fetch the current chain head for this tenant. We order by
        # ``(timestamp DESC, id DESC)`` so concurrent writes with the
        # same timestamp still pick a deterministic tail; ``verify_chain``
        # walks in the reverse of this order so the two agree.
        head_stmt = (
            select(AuditLog.self_hash)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
        prev_hash = (await db.execute(head_stmt)).scalar_one_or_none()

        # Naive UTC matches the convention used in identity_upsert /
        # entity_resolution so the same value round-trips across SQLite
        # and Postgres without triggering the aware/naive comparison trap.
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        row_id = str(uuid.uuid4())

        self_hash = _sha256_hex(
            _canonical_payload(
                prev_hash=prev_hash,
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                timestamp=timestamp,
            )
        )

        row = AuditLog(
            id=row_id,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            timestamp=timestamp,
            ip_address=ip_address,
            prev_hash=prev_hash,
            self_hash=self_hash,
        )
        db.add(row)
        if flush_only:
            await db.flush()
        else:
            await db.commit()
            await db.refresh(row)
        return row


async def verify_chain(db: AsyncSession, *, tenant_id: str | None) -> VerifyResult:
    """Walk the full audit chain for *tenant_id* and re-verify each row.

    At each position we check two independent invariants:

      1. ``prev_hash`` equals the previous row's ``self_hash`` (linkage).
      2. Recomputing SHA-256 over the canonical payload produces the
         stored ``self_hash`` (content integrity).

    If either check fails we stop and report the index of the first
    failing row. A missing row anywhere in the history breaks linkage at
    the first position after the gap, so delete-tampering is detected with
    the same machinery.
    """
    stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.timestamp, AuditLog.id)
    rows = (await db.execute(stmt)).scalars().all()

    # Rows written before the chain existed carry no hashes at all. Verifying
    # them against a recomputed digest compares something to NULL and fails, and
    # the failure this function used to report was
    #
    #     self_hash mismatch (row content tampered)
    #
    # — an accusation of evidence tampering, raised on every deployment that
    # predates the hash chain, in the one part of the product whose value is
    # that its answer can be trusted. On this machine that was four rows out of
    # four: a red "integrity broken" banner across an application that was
    # working perfectly.
    #
    # They are counted and skipped, not back-filled. Hashing them now would be
    # trivial and would be a lie: it would present rows whose integrity was
    # never protected as verified, which is the exact thing this chain exists to
    # make impossible.
    legacy_unhashed = 0
    start = 0
    for row in rows:
        if row.self_hash is None and row.prev_hash is None:
            legacy_unhashed += 1
            start += 1
            continue
        break

    expected_prev: str | None = None
    for idx, row in enumerate(rows[start:], start=start):
        # A row with no hash *after* the chain has begun is a different animal
        # from a legacy row: the writer that produced it skipped the chain, or
        # somebody replaced a row with an unhashed one. Neither is "tampered
        # content", and neither is fine.
        if row.self_hash is None:
            return VerifyResult(
                ok=False,
                broken_at=idx,
                reason="unhashed row inside the chain (written without the chain writer, or replaced)",
                legacy_unhashed=legacy_unhashed,
                verified=idx - start,
            )

        if row.prev_hash != expected_prev:
            return VerifyResult(
                ok=False,
                broken_at=idx,
                reason="prev_hash mismatch (linkage broken)",
                legacy_unhashed=legacy_unhashed,
                verified=idx - start,
            )

        recomputed = _sha256_hex(
            _canonical_payload(
                prev_hash=row.prev_hash,
                tenant_id=row.tenant_id,
                user_id=row.user_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                details=row.details,
                timestamp=row.timestamp,
            )
        )
        if recomputed != row.self_hash:
            return VerifyResult(
                ok=False,
                broken_at=idx,
                reason="self_hash mismatch (row content tampered)",
                legacy_unhashed=legacy_unhashed,
                verified=idx - start,
            )

        expected_prev = row.self_hash

    return VerifyResult(
        ok=True,
        broken_at=None,
        reason=None,
        legacy_unhashed=legacy_unhashed,
        verified=len(rows) - start,
    )


__all__ = ["VerifyResult", "write_audit", "verify_chain"]
