"""Unit tests for shared.domain.normalization.

These are pure-function tests — no DB, no async. They lock in the contracts
that the rest of the correlation engine relies on: the UNIQUE constraint on
identities, the fuzzy-dedup Hamming threshold for leaks, and the identity
collapse rules operators care about (Gmail aliases, domain case folding).
"""

from __future__ import annotations

import pytest

from shared.domain.normalization import (
    hamming_distance,
    normalize_content,
    normalize_identifier,
    simhash64,
)

# ─── Identifier normalization ────────────────────────────────────────────────


class TestNormalizeEmail:
    def test_lowercases_and_strips(self):
        assert normalize_identifier("  Foo@Example.COM  ", "email") == "foo@example.com"

    def test_gmail_collapses_dots(self):
        assert normalize_identifier("f.oo.bar@gmail.com", "email") == "foobar@gmail.com"

    def test_gmail_strips_plus_alias(self):
        assert normalize_identifier("foo+newsletter@gmail.com", "email") == "foo@gmail.com"

    def test_gmail_combined_rules(self):
        assert normalize_identifier("F.Bar+promo@GoogleMail.com", "email") == "fbar@gmail.com"

    def test_non_gmail_keeps_dots(self):
        assert normalize_identifier("f.oo@corp.example.com", "email") == "f.oo@corp.example.com"

    def test_non_gmail_still_strips_plus_alias(self):
        assert normalize_identifier("foo+tag@corp.example.com", "email") == "foo@corp.example.com"

    def test_empty_or_malformed_does_not_crash(self):
        assert normalize_identifier("", "email") == ""
        assert normalize_identifier(None, "email") == ""
        # No @ sign: treat as generic lowercase.
        assert normalize_identifier("notanemail", "email") == "notanemail"


class TestNormalizeDomain:
    def test_drops_protocol_and_www(self):
        assert normalize_identifier("https://www.Example.com/", "domain") == "example.com"

    def test_strips_trailing_dot(self):
        assert normalize_identifier("example.com.", "domain") == "example.com"


class TestNormalizeUsername:
    def test_strips_leading_at_and_lowercases(self):
        assert normalize_identifier("@FooBar_42", "username") == "foobar_42"

    def test_drops_exotic_punctuation(self):
        assert normalize_identifier("foo!bar$", "username") == "foobar"


class TestNormalizePhone:
    def test_digits_only(self):
        assert normalize_identifier("+1 (415) 555-0199", "phone") == "14155550199"


class TestNormalizeWallet:
    def test_preserves_case_for_checksum(self):
        raw = "0xAbCdEf0123456789abcdef0123456789abcdef12"
        assert normalize_identifier(raw, "eth") == raw


class TestNormalizeUnknownType:
    def test_falls_back_to_generic_nfkc_lower_strip(self):
        assert normalize_identifier("  Bïrd  ", "unknown-type") == "bïrd"


# ─── Content + SimHash ───────────────────────────────────────────────────────


class TestNormalizeContent:
    def test_collapses_whitespace(self):
        assert normalize_content("foo   \n\n bar\t") == "foo bar"

    def test_lowercases(self):
        assert normalize_content("FOO Bar") == "foo bar"

    def test_preserves_email_structure(self):
        assert "user@example.com" in normalize_content("Contact user@example.com NOW!")

    def test_empty_input(self):
        assert normalize_content("") == ""
        assert normalize_content(None) == ""


class TestSimhash:
    SAMPLE = (
        "password leak for acme corp, 14000 records, including emails and hashed passwords "
        "from the forum breach of 2023"
    )

    def test_deterministic(self):
        assert simhash64(self.SAMPLE) == simhash64(self.SAMPLE)

    def test_empty_returns_zero(self):
        assert simhash64("") == 0

    def test_near_duplicate_is_close(self):
        """Whitespace / punctuation variants should land within Hamming ≤ 3."""
        variant = "  Password leak for ACME corp.  14000 records, including emails and hashed passwords from the forum breach of 2023  "
        a = simhash64(normalize_content(self.SAMPLE))
        b = simhash64(normalize_content(variant))
        assert hamming_distance(a, b) <= 3, f"near-dup should be close, got {hamming_distance(a, b)}"

    def test_different_content_is_far(self):
        other = (
            "cryptocurrency wallet addresses dumped from discord channel, 300 btc and 2000 eth "
            "recovered from phishing site takedown"
        )
        a = simhash64(normalize_content(self.SAMPLE))
        b = simhash64(normalize_content(other))
        assert hamming_distance(a, b) > 10, f"unrelated texts should be far apart, got {hamming_distance(a, b)}"

    def test_fits_in_signed_bigint(self):
        # BigInteger maps to signed 64-bit in both Postgres and SQLite.
        v = simhash64(self.SAMPLE)
        assert -(1 << 63) <= v <= (1 << 63) - 1


class TestHammingDistance:
    def test_identical(self):
        assert hamming_distance(42, 42) == 0

    def test_single_bit_flip(self):
        assert hamming_distance(0, 1) == 1
        assert hamming_distance(0b1010, 0b1000) == 1

    def test_handles_signed_representation(self):
        # Values at the signed/unsigned boundary round-trip cleanly.
        neg = -1  # all 1s in two's complement 64-bit
        assert hamming_distance(neg, 0) == 64


# ─── Contract: normalization is idempotent ──────────────────────────────────


@pytest.mark.parametrize(
    "raw,type_",
    [
        ("F.Bar+promo@GoogleMail.com", "email"),
        ("https://www.Example.COM/", "domain"),
        ("@Foo", "username"),
        ("+1 (415) 555-0199", "phone"),
    ],
)
def test_normalization_is_idempotent(raw, type_):
    once = normalize_identifier(raw, type_)
    twice = normalize_identifier(once, type_)
    assert once == twice, f"expected idempotent, got {once!r} → {twice!r}"
