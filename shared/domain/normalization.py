"""Identifier + content normalization used across the correlation engine.

Two jobs live in this module:

1. **Identifier canonicalization** (``normalize_identifier``) — turns an
   observed identifier string into the unique key we store in
   ``identities.normalized_identifier``. This is what the `UNIQUE
   (tenant_id, type, normalized_identifier)` constraint is built on, so the
   rules here directly decide which raw forms collapse to the same row
   (e.g. ``F.Bar+promo@googlemail.com`` and ``fbar@gmail.com`` → same entity).

2. **Content fingerprinting** (``normalize_content`` + ``simhash64``) — used
   for fuzzy leak dedup. ``normalize_content`` is cheap and deterministic;
   ``simhash64`` returns a 64-bit fingerprint whose Hamming distance
   approximates the Jaccard distance of the original tokens. Two leaks with
   Hamming distance ≤ 3 are considered near-duplicates.

Both functions are **pure** and **deterministic** — no DB, no network, no
randomness. This matters: the UNIQUE constraint depends on the same bytes
being produced for the same input across processes and DB upgrades.
"""

from __future__ import annotations

import re
import unicodedata
from hashlib import blake2b

# ─── Identifier normalization ────────────────────────────────────────────────

_EMAIL_ALIAS_RE = re.compile(r"\+[^@]*$")
_PHONE_STRIP_RE = re.compile(r"[^\d]")
_NON_ALPHANUM_RE = re.compile(r"[^a-z0-9_.\-]")


def _nfkc(s: str) -> str:
    """Unicode normalize (NFKC) + strip + lower. A base step for every type."""
    return unicodedata.normalize("NFKC", s).strip().lower()


def _normalize_email(raw: str) -> str:
    s = _nfkc(raw)
    if "@" not in s:
        return s
    local, _, domain = s.rpartition("@")
    # Googlemail was the original UK/DE brand — collapse to gmail so aliases
    # across the two domains unify.
    if domain == "googlemail.com":
        domain = "gmail.com"
    if domain == "gmail.com":
        # Gmail: dots are ignored, "+tag" is an alias suffix.
        local = local.replace(".", "")
        local = _EMAIL_ALIAS_RE.sub("", local)
    else:
        # For other providers only the "+tag" convention is safely universal.
        local = _EMAIL_ALIAS_RE.sub("", local)
    return f"{local}@{domain}"


def _normalize_domain(raw: str) -> str:
    s = _nfkc(raw)
    # Strip protocol + trailing slash + trailing dot (root label).
    s = re.sub(r"^[a-z]+://", "", s)
    s = s.rstrip("/").rstrip(".")
    # "www." is almost always a noise prefix for correlation.
    if s.startswith("www."):
        s = s[4:]
    return s


def _normalize_username(raw: str) -> str:
    s = _nfkc(raw)
    # Strip leading @ (Twitter/Telegram convention) and any non-handle chars.
    s = s.lstrip("@")
    s = _NON_ALPHANUM_RE.sub("", s)
    return s


def _normalize_phone(raw: str) -> str:
    # Keep only digits; if the caller prefixed with '+' we still drop it —
    # the country code, if present, remains as leading digits.
    return _PHONE_STRIP_RE.sub("", raw)


def _normalize_wallet(raw: str) -> str:
    # Crypto wallet addresses are case-sensitive for checksums (e.g. EIP-55),
    # so we only strip surrounding whitespace. Do NOT lowercase.
    return raw.strip()


def _normalize_generic(raw: str) -> str:
    return _nfkc(raw)


_NORMALIZERS = {
    "email": _normalize_email,
    "domain": _normalize_domain,
    "organization": _normalize_domain,  # orgs are keyed by their domain in NASO
    "username": _normalize_username,
    "handle": _normalize_username,
    "person": _normalize_generic,
    "phone": _normalize_phone,
    "btc": _normalize_wallet,
    "eth": _normalize_wallet,
    "crypto": _normalize_wallet,
    "credential": _normalize_generic,
}


def normalize_identifier(identifier: str, type_: str | None = None) -> str:
    """Return the canonical form of *identifier* given its *type*.

    Unknown types fall through to a generic NFKC-lower-strip. We never return
    ``None`` and never raise for empty strings: callers should validate
    upstream and refuse empty identifiers before hitting the database.
    """
    if identifier is None:
        return ""
    fn = _NORMALIZERS.get((type_ or "").lower(), _normalize_generic)
    return fn(identifier)


# ─── Content fingerprinting ──────────────────────────────────────────────────

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_content(raw: str) -> str:
    """Flatten whitespace + lowercase. Input to both exact-dedup and simhash.

    We intentionally keep punctuation that participates in identifiers
    (``@ . - _``) so emails and URLs survive the pass; everything else
    becomes whitespace before collapse.
    """
    if not raw:
        return ""
    s = unicodedata.normalize("NFKC", raw).lower()
    # Keep word characters and identifier-ish punctuation; everything else → space.
    s = re.sub(r"[^a-z0-9@._\-+\s]", " ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def _feature_hash(feature: str) -> int:
    """64-bit unsigned hash for a single feature token. blake2b is fast and
    distributes uniformly — what simhash needs."""
    return int.from_bytes(blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def simhash64(text: str, n_gram: int = 3) -> int:
    """Charikar-style 64-bit SimHash over word n-grams.

    n-grams outperform bag-of-words for near-duplicate detection because they
    capture local order. n=3 is a sensible default for short-to-medium leak
    bodies; bump it up for long articles.

    Returns a **signed** 64-bit int so the value round-trips through a
    ``BigInteger`` column without overflow. Callers that want to compare
    Hamming distance should use :func:`hamming_distance` which handles the
    sign-to-unsigned conversion internally.
    """
    if not text:
        return 0
    tokens = _WORD_RE.findall(text.lower())
    if not tokens:
        return 0
    if len(tokens) >= n_gram:
        features = [" ".join(tokens[i : i + n_gram]) for i in range(len(tokens) - n_gram + 1)]
    else:
        features = tokens

    weights = [0] * 64
    for feat in features:
        h = _feature_hash(feat)
        for bit in range(64):
            if (h >> bit) & 1:
                weights[bit] += 1
            else:
                weights[bit] -= 1

    unsigned = 0
    for bit in range(64):
        if weights[bit] > 0:
            unsigned |= 1 << bit
    return _to_signed_64(unsigned)


def _to_signed_64(u: int) -> int:
    return u - (1 << 64) if u >= (1 << 63) else u


def _to_unsigned_64(s: int) -> int:
    return s + (1 << 64) if s < 0 else s


def hamming_distance(a: int, b: int) -> int:
    """Popcount of the XOR of two (possibly signed) 64-bit SimHash values."""
    xor = _to_unsigned_64(a) ^ _to_unsigned_64(b)
    # Python's int.bit_count exists on 3.10+. Fall back to manual popcount.
    try:
        return xor.bit_count()
    except AttributeError:  # pragma: no cover — pre-3.10 safety net
        return bin(xor).count("1")


__all__ = [
    "normalize_identifier",
    "normalize_content",
    "simhash64",
    "hamming_distance",
]
