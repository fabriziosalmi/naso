"""Unit tests for shared/utils/sec_handoff.py — the naso ↔ fabgpt-sec contract.

Covers: redaction (no raw PII in the emitted finding), shape match (matches
NasoFinding fields fabgpt-sec expects), HMAC signature build + verify round-trip.

The HTTP endpoints in backend/app/api/endpoints/sec.py are thin glue over
this helper + the DB session; they're exercised in the broader e2e suite when
sec is wired up live.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from shared.utils.sec_handoff import (
    build_soar_request,
    leak_to_naso_finding,
    verify_signature,
)


def _leak(
    leak_id: str = "leak-1",
    source: str = "darkweb_forum_a",
    severity: int = 92,
    discovered_at=None,
    content_snippet: str = "raw user@example.com leaked here 192.168.1.1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=leak_id,
        source=source,
        severity_score=severity,
        discovered_at=discovered_at or datetime(2026, 6, 16, 8, 30, 0, tzinfo=UTC),
        content_snippet=content_snippet,
        normalized_content=content_snippet.lower(),
    )


def _identity(
    identifier: str = "user@example.com",
    type_: str = "email",
    confidence: float = 0.95,
    is_protected: bool = False,
    master_id: str | None = "cluster-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id="id-1",
        identifier=identifier,
        type=type_,
        confidence=confidence,
        is_protected=is_protected,
        master_identity_id=master_id,
    )


def test_finding_shape_matches_naso_contract():
    f = leak_to_naso_finding(_leak(), [_identity()])
    # exact field set fabgpt-sec/sensors/_naso_models.py expects
    assert set(f.keys()) == {
        "id",
        "severity_score",
        "kind",
        "target",
        "observed_at",
        "identity",
        "source_chain",
        "confidence",
    }
    assert f["severity_score"] == 92
    assert f["observed_at"] == "2026-06-16T08:30:00Z"
    assert f["target"]["kind"] == "email"
    assert "identifier_hash" in f["target"]
    assert f["identity"]["cluster_id"] == "cluster-1"
    assert f["source_chain"] == ["darkweb_forum_a", "naso_correlator"]


def test_finding_redaction_strips_raw_pii():
    """No raw email/IP from content_snippet may appear anywhere in the wire payload."""
    leak = _leak()
    f = leak_to_naso_finding(leak, [_identity(identifier="user@example.com")])
    blob = json.dumps(f, ensure_ascii=False)
    assert "user@example.com" not in blob
    assert "192.168.1.1" not in blob
    assert "raw user@example.com" not in blob  # content_snippet must not bleed in


def test_finding_handles_no_identities():
    f = leak_to_naso_finding(_leak(), [])
    assert f["target"]["kind"] == "leak"
    assert f["target"]["leak_id"] == "leak-1"
    assert f["identity"] == {}


def test_finding_picks_highest_confidence_identity():
    a = _identity(identifier="low@x.test", confidence=0.4)
    a.id = "a"
    b = _identity(identifier="high@x.test", confidence=0.9)
    b.id = "b"
    f = leak_to_naso_finding(_leak(), [a, b])
    # the picked identity is hashed; we just check via re-hashing the high one
    expected_hash = hashlib.sha256(b"high@x.test").hexdigest()[:16]
    assert f["target"]["identifier_hash"] == expected_hash


def test_soar_request_headers_present_and_signature_verifies():
    finding = leak_to_naso_finding(_leak(), [_identity()])
    headers, body = build_soar_request(finding, secret="shared-secret-xyz")
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Naso-Signature"].startswith("sha256=")
    assert len(headers["X-Naso-Nonce"]) >= 16
    assert headers["X-Naso-Issued-At"].endswith("Z")
    assert verify_signature("shared-secret-xyz", body, headers["X-Naso-Signature"]) is True


def test_soar_signature_rejects_tampered_body():
    finding = leak_to_naso_finding(_leak(), [_identity()])
    _, body = build_soar_request(finding, secret="shared-secret-xyz")
    # naive tamper: flip a single byte in a position guaranteed to be inside the JSON content
    tampered = body[:-1] + (b"X" if body[-1:] != b"X" else b"Y")
    # recompute what the receiver would compute on the tampered body — must NOT match
    sig_for_original = "sha256=" + hmac.new(b"shared-secret-xyz", body, hashlib.sha256).hexdigest()
    assert verify_signature("shared-secret-xyz", tampered, sig_for_original) is False


def test_soar_request_requires_secret():
    finding = leak_to_naso_finding(_leak(), [_identity()])
    with pytest.raises(ValueError):
        build_soar_request(finding, secret="")


def test_soar_body_is_deterministic_for_same_finding():
    """Same finding, same body bytes (sorted keys + compact separators). Tests rely on it."""
    finding = leak_to_naso_finding(_leak(), [_identity()])
    _, body1 = build_soar_request(finding, secret="s", nonce="n", issued_at="2026-06-16T08:30:00Z")
    _, body2 = build_soar_request(finding, secret="s", nonce="n", issued_at="2026-06-16T08:30:00Z")
    assert body1 == body2
