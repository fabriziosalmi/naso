"""AhmiaClient hardening — pagination, retry, breaker, provenance, sanitize.

All tests wire an ``httpx.AsyncClient`` with a ``MockTransport`` so
zero real network traffic is generated. Scenarios cover the hardening
contract introduced by the Tor/Ahmia round:

  * Query sanitization rejects empty / oversized / control-char queries.
  * Multi-page fetch stops on empty page and annotates provenance.
  * 5xx responses trigger bounded retries with backoff.
  * 4xx (non-429) fails fast.
  * Circuit breaker trips after repeated failures and refuses further
    requests until recovery.
  * Duplicate URLs across pages are deduplicated and counted.
  * ``via_tor`` flag reflects the configured proxy.
"""
from __future__ import annotations

import pytest
import httpx

from shared.domain.services.dark_web.ahmia_client import (
    AhmiaClient,
    AhmiaUnavailable,
    InvalidQuery,
    sanitize_query,
)
from shared.domain.services.dark_web.circuit_breaker import CircuitBreaker
from shared.domain.services.dark_web.config import DarkWebConfig
from shared.domain.services.dark_web.rate_limiter import TokenBucket


# asyncio marker applied per-class so the sync sanitize tests don't warn.


# ─── HTML fixtures ───────────────────────────────────────────────────────────

def _page_html(results: list[tuple[str, str, str]]) -> str:
    """Build an Ahmia-like page with a list of (title, url, description)."""
    items = "\n".join(
        f"""
        <li class="result">
            <h4>{title}</h4>
            <p class="onion-site">{url}</p>
            <p class="description">{desc}</p>
        </li>
        """
        for title, url, desc in results
    )
    return f"<html><body><ul>{items}</ul></body></html>"


EMPTY_PAGE = "<html><body><p>No results</p></body></html>"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fast_config(**overrides) -> DarkWebConfig:
    """DarkWebConfig with tiny timeouts + no real retries for test speed."""
    defaults = dict(
        max_pages=3,
        connect_timeout=0.5,
        read_timeout=0.5,
        max_retries=2,
        retry_base_delay=0.01,
        retry_max_delay=0.05,
        failure_threshold=3,
        recovery_timeout=0.5,
        rate_tokens_per_second=1000.0,  # effectively disabled for tests
        rate_burst=1000,
    )
    defaults.update(overrides)
    return DarkWebConfig(**defaults)


def _client_with_handler(handler, config: DarkWebConfig | None = None) -> AhmiaClient:
    cfg = config or _fast_config()
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(
        transport=transport,
        headers={"User-Agent": cfg.user_agent},
        follow_redirects=True,
    )
    return AhmiaClient(
        config=cfg,
        http_client=http,
        token_bucket=TokenBucket(cfg.rate_tokens_per_second, cfg.rate_burst),
        breaker=CircuitBreaker(
            failure_threshold=cfg.failure_threshold,
            recovery_timeout=cfg.recovery_timeout,
        ),
    )


# ─── Query sanitization ──────────────────────────────────────────────────────

class TestSanitizeQuery:
    def test_strips_control_chars(self):
        assert sanitize_query("foo\x00bar\x1f", min_len=1, max_len=50) == "foobar"

    def test_collapses_whitespace(self):
        assert sanitize_query("  foo   bar\t\nbaz  ", min_len=1, max_len=50) == "foo bar baz"

    def test_rejects_too_short(self):
        with pytest.raises(InvalidQuery):
            sanitize_query("", min_len=2, max_len=50)
        with pytest.raises(InvalidQuery):
            sanitize_query("a", min_len=2, max_len=50)

    def test_rejects_too_long(self):
        with pytest.raises(InvalidQuery):
            sanitize_query("x" * 100, min_len=1, max_len=50)

    def test_rejects_none(self):
        with pytest.raises(InvalidQuery):
            sanitize_query(None, min_len=1, max_len=50)


# ─── Pagination ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPagination:
    async def test_fetches_multiple_pages(self):
        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params.get("d", "1"))
            if page <= 2:
                return httpx.Response(200, html=_page_html([
                    (f"Title {page}-A", f"url-{page}-a.onion", "desc"),
                    (f"Title {page}-B", f"url-{page}-b.onion", "desc"),
                ]))
            return httpx.Response(200, html=EMPTY_PAGE)

        client = _client_with_handler(handler)
        report = await client.search("breach")
        assert report.pages_fetched == 3  # page 3 was fetched, returned empty
        assert len(report.results) == 4
        assert {r.page for r in report.results} == {1, 2}

    async def test_deduplicates_urls_across_pages(self):
        """If page 2 returns URLs already seen on page 1, they are dropped."""
        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params.get("d", "1"))
            results = [
                ("A", "dup-url.onion", "desc"),
                ("B", f"unique-{page}.onion", "desc"),
            ]
            return httpx.Response(200, html=_page_html(results))

        client = _client_with_handler(handler, config=_fast_config(max_pages=3))
        report = await client.search("breach")
        urls = {r.url for r in report.results}
        # dup-url.onion appears once, unique-1..3.onion appear once each.
        assert "dup-url.onion" in urls
        assert "unique-1.onion" in urls
        assert report.duplicates_dropped >= 2  # pages 2 and 3 contributed dups


# ─── Retry / failure handling ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRetry:
    async def test_retries_on_5xx_then_succeeds(self):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, html=_page_html([("T", "u.onion", "d")]))

        # Bound to 1 page so the test counts page-1 retries, not follow-on
        # successful page-2 fetches that would pollute the call count.
        client = _client_with_handler(handler, config=_fast_config(max_pages=1))
        report = await client.search("breach")
        assert len(report.results) >= 1
        assert call_count["n"] == 3

    async def test_gives_up_after_max_retries_on_5xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = _client_with_handler(handler)
        # With max_retries=2 we attempt 3 times total for page 1, then the
        # search aborts (returning partial report, in this case empty).
        report = await client.search("breach")
        assert len(report.results) == 0
        assert report.pages_fetched == 0  # no page succeeded

    async def test_does_not_retry_on_4xx_non_429(self):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(403)

        client = _client_with_handler(handler)
        report = await client.search("breach")
        # 4xx → no retry, fail page fast, search loop breaks → 1 HTTP call.
        assert call_count["n"] == 1
        assert len(report.results) == 0

    async def test_retries_on_timeout(self):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, html=_page_html([("T", "u.onion", "d")]))

        client = _client_with_handler(handler, config=_fast_config(max_pages=1))
        report = await client.search("breach")
        assert len(report.results) >= 1
        assert call_count["n"] == 2


# ─── Circuit breaker ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCircuitBreaker:
    async def test_trips_after_threshold_and_rejects_further_calls(self):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(500)

        cfg = _fast_config(failure_threshold=2, max_retries=0, max_pages=5)
        client = _client_with_handler(handler, config=cfg)

        # First search — uses 1 attempt for page 1. Failure count=1. Search
        # stops (500 with no retries). Breaker not tripped yet.
        await client.search("breach one")
        assert client._breaker.state in ("closed", "open")
        failures_before = call_count["n"]

        # Second search — attempt hits 500, failure count=2, breaker trips.
        await client.search("breach two")
        assert client._breaker.state == "open"
        failures_after = call_count["n"]
        assert failures_after > failures_before

        # Third search — breaker is open, NO new HTTP call should fire.
        before_third = call_count["n"]
        await client.search("breach three")
        assert call_count["n"] == before_third, (
            "open breaker must not forward requests to the transport"
        )


# ─── Provenance ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestProvenance:
    async def test_results_carry_fetched_at_page_and_source(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, html=_page_html([("T", "u.onion", "d")]))

        client = _client_with_handler(handler, config=_fast_config(max_pages=1))
        report = await client.search("breach")
        assert report.results
        r = report.results[0]
        assert r.source == "ahmia"
        assert r.page == 1
        assert r.fetched_at  # ISO timestamp
        assert r.via_tor is False  # no tor_proxy_url configured

    async def test_via_tor_true_when_proxy_configured(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, html=_page_html([("T", "u.onion", "d")]))

        # Build client with tor_proxy_url configured — we override the
        # http client so no actual proxy connection is attempted.
        cfg = _fast_config()
        cfg = DarkWebConfig(
            **{**cfg.__dict__, "tor_proxy_url": "socks5://naso-tor-cluster:8118"}
        )
        transport = httpx.MockTransport(handler)
        http = httpx.AsyncClient(transport=transport)
        client = AhmiaClient(
            config=cfg,
            http_client=http,
            token_bucket=TokenBucket(cfg.rate_tokens_per_second, cfg.rate_burst),
            breaker=CircuitBreaker(
                failure_threshold=cfg.failure_threshold,
                recovery_timeout=cfg.recovery_timeout,
            ),
        )
        report = await client.search("breach")
        assert report.results and report.results[0].via_tor is True


# ─── Legacy façade ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestFacadePreservesLegacyShape:
    async def test_dict_has_title_url_description(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, html=_page_html([("T", "u.onion", "D")]))

        client = _client_with_handler(handler, config=_fast_config(max_pages=1))
        report = await client.search("breach")
        d = report.results[0].as_dict()
        # Legacy UI depends on these three keys; provenance keys are extra.
        assert set(["title", "url", "description"]).issubset(set(d.keys()))
        assert d["title"] == "T"
        assert d["url"] == "u.onion"
        assert d["description"] == "D"
