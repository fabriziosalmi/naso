"""Handoff helpers to fabgpt-sec (the AIMP-protocol security peer).

This module owns the contract between naso (backend / ingestion / correlation)
and fabgpt-sec (HITL + tarpit-policy + gossip). Two responsibilities:

  1. leak_to_naso_finding(leak, identities) → JSON-serializable dict that
     matches the NasoFinding shape fabgpt-sec expects (see fabgptsec/
     sensors/_naso_models.py:NasoFinding.from_wire).

  2. build_soar_request(finding, secret) → (headers, body_bytes) ready to
     POST to fabgpt-sec's /api/soar/inbound endpoint. HMAC-SHA256 signature
     over the raw body + nonce + ISO timestamp; sec verifies with the same
     shared secret.

REDACTION CONTRACT: raw PII NEVER leaves this module. Identity identifiers
(email, phone, username, ip) are hashed (SHA-256, first 16 hex chars) and
emitted under {kind, identifier_hash}. Free-text content_snippet is NOT
emitted (it lives only in naso's storage). If a future field carries
sensitive data, this module is the chokepoint to update.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any


def _utc_iso(dt) -> str:
    """ISO-8601 UTC, second precision, suffix 'Z'."""
    if dt is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _primary_identity(identities: Iterable[Any]) -> Any | None:
    """Pick the highest-confidence identity from the bag (deterministic on ties via id)."""
    arr = list(identities or [])
    if not arr:
        return None
    return sorted(
        arr,
        key=lambda i: (-(getattr(i, "confidence", 1.0) or 0.0), str(getattr(i, "id", ""))),
    )[0]


def leak_to_naso_finding(leak: Any, identities: Iterable[Any] = ()) -> dict[str, Any]:
    """Map a naso LeakHit + its related identities to a NasoFinding-shape dict
    (fabgpt-sec contract). Strips content_snippet, hashes identifier values.

    The caller is responsible for fetching `identities` (typically via the
    LeakHit.identities relationship); we keep the function pure.
    """
    primary = _primary_identity(identities)
    target: dict[str, Any] = {"kind": "leak", "leak_id": str(getattr(leak, "id", ""))}
    identity_blob: dict[str, Any] = {}
    if primary is not None:
        target = {
            "kind": getattr(primary, "type", "identity") or "identity",
            "identifier_hash": _hash_identifier(getattr(primary, "identifier", "") or ""),
        }
        identity_blob = {
            "cluster_id": str(getattr(primary, "master_identity_id", "") or "") or None,
            "confidence": float(getattr(primary, "confidence", 1.0) or 1.0),
            "is_protected": bool(getattr(primary, "is_protected", False)),
        }
    source = str(getattr(leak, "source", "") or "unknown")
    return {
        "id": str(getattr(leak, "id", "") or ""),
        "severity_score": int(getattr(leak, "severity_score", 0) or 0),
        "kind": source,
        "target": target,
        "observed_at": _utc_iso(getattr(leak, "discovered_at", None)),
        "identity": identity_blob,
        "source_chain": [source, "naso_correlator"],
        # naso's own classifier confidence isn't a column today — leave None so
        # fabgpt-sec consults its second-opinion classifier when configured.
        "confidence": None,
    }


def build_soar_request(
    finding: dict[str, Any],
    *,
    secret: str,
    nonce: str | None = None,
    issued_at: str | None = None,
) -> tuple[dict[str, str], bytes]:
    """Build (headers, body) ready to POST to fabgpt-sec /api/soar/inbound.

    Headers expected by sec (see fabgptsec/sensors/naso_soar.py):
      X-Naso-Signature  sha256=<hex(hmac_sha256(body, secret))>
      X-Naso-Nonce      <urlsafe random token, >= 16 bytes>
      X-Naso-Issued-At  <ISO UTC second precision>
      Content-Type      application/json
    """
    if not secret:
        raise ValueError("secret is required (FABGPTSEC_NASO_SOAR_SECRET / NASO_SOAR_HMAC_SECRET)")
    body_bytes = json.dumps(finding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Naso-Signature": sig,
        "X-Naso-Nonce": nonce or secrets.token_urlsafe(18),
        "X-Naso-Issued-At": issued_at or _utc_iso(None),
    }
    return headers, body_bytes


def verify_signature(secret: str, body_bytes: bytes, signature_header: str) -> bool:
    """Symmetric verifier — useful for tests + for any naso-side audit path."""
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
