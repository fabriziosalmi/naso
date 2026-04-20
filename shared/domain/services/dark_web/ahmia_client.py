"""Hardened Ahmia search client.

Replaces the single-shot ``httpx.AsyncClient().get(AHMIA_URL, params=q)``
call that shipped the first revision of NASO with a production-grade
pipeline:

    1. **Query sanitization** — length bounds and control-char stripping
       before the query hits the wire. Rejects empty / oversized probes
       instead of silently returning Ahmia's landing page.
    2. **Rate limiting** — a shared :class:`TokenBucket` throttles egress
       so NASO is a polite citizen of the Ahmia community resource.
    3. **Circuit breaker** — :class:`CircuitBreaker` stops hammering after
       consecutive failures and probes for recovery once ``recovery_timeout``
       has elapsed.
    4. **Retry with jittered exponential backoff** — 5xx responses and
       timeouts are retried up to ``max_retries`` times; 4xx (except 429)
       are propagated immediately.
    5. **Pagination** — up to ``max_pages`` are fetched in sequence.
       Duplicate-URL detection short-circuits when a page returns only
       previously-seen results.
    6. **Provenance** — every result is tagged with ``fetched_at``,
       ``page``, ``source="ahmia"``, and ``via_tor`` (True when the HTTP
       client is configured to route through the local Tor cluster), so
       downstream correlation and audit have the metadata they need.

The class accepts an injectable ``httpx.AsyncClient`` so tests can point
it at ``MockTransport`` without real network access.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .config import DEFAULT_CONFIG, DarkWebConfig
from .rate_limiter import TokenBucket

logger = logging.getLogger("naso-darkweb-ahmia")


class InvalidQuery(ValueError):
    """Raised when the caller-supplied query fails sanitization."""


class AhmiaUnavailable(RuntimeError):
    """Raised when Ahmia is unreachable after retries or the breaker is open."""


@dataclass
class AhmiaResult:
    """One search hit, enriched with provenance."""

    title: str
    url: str
    description: str
    fetched_at: str
    page: int
    source: str = "ahmia"
    via_tor: bool = False

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "fetched_at": self.fetched_at,
            "page": self.page,
            "source": self.source,
            "via_tor": self.via_tor,
        }


@dataclass
class AhmiaSearchReport:
    """Full report of a multi-page search. ``results`` is the deduplicated
    union; per-page diagnostics help the UI render "page 3 of 5 (47 hits)".
    """

    query: str
    results: list[AhmiaResult] = field(default_factory=list)
    pages_fetched: int = 0
    duplicates_dropped: int = 0
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.as_dict() for r in self.results],
            "pages_fetched": self.pages_fetched,
            "duplicates_dropped": self.duplicates_dropped,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


# ─── Query sanitization ──────────────────────────────────────────────────────

# Strip ASCII control chars EXCEPT tab (0x09), newline (0x0A), and CR (0x0D)
# — those are whitespace handled by the collapse pass below, and stripping
# them outright would merge "foo\nbar" into "foobar" (bug fixed in R7-h1).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_query(raw: str, *, min_len: int, max_len: int) -> str:
    """Normalize + length-check a query. Raises ``InvalidQuery`` on bad input.

    Rules:
      * ``NFKC`` normalize to collapse visual-confusable characters.
      * Strip control chars (they can break the URL encoder or, worse,
        smuggle headers).
      * Collapse whitespace to single spaces.
      * Trim outer whitespace.
      * Enforce ``[min_len, max_len]`` bounds.
    """
    if raw is None:
        raise InvalidQuery("query is required")
    s = unicodedata.normalize("NFKC", str(raw))
    s = _CONTROL_CHARS_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) < min_len:
        raise InvalidQuery(f"query too short: need at least {min_len} char(s)")
    if len(s) > max_len:
        raise InvalidQuery(f"query too long: {len(s)} chars (max {max_len})")
    return s


# ─── Client ──────────────────────────────────────────────────────────────────

class AhmiaClient:
    """Hardened Ahmia search client.

    Instances are cheap to create but also cheap to reuse — the underlying
    httpx client is long-lived, so pass the same instance to subsequent
    searches when possible to reuse connections.
    """

    def __init__(
        self,
        *,
        config: Optional[DarkWebConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        token_bucket: Optional[TokenBucket] = None,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self._config = config or DEFAULT_CONFIG
        self._http = http_client or self._build_default_client(self._config)
        self._bucket = token_bucket or TokenBucket(
            tokens_per_second=self._config.rate_tokens_per_second,
            burst=self._config.rate_burst,
        )
        self._breaker = breaker or CircuitBreaker(
            failure_threshold=self._config.failure_threshold,
            recovery_timeout=self._config.recovery_timeout,
        )
        self._via_tor = bool(self._config.tor_proxy_url)

    @staticmethod
    def _build_default_client(config: DarkWebConfig) -> httpx.AsyncClient:
        # Assembled once per client instance; subsequent searches reuse
        # connections from the underlying pool (big win for multi-page
        # fetches, which otherwise pay TLS setup 5× per probe).
        timeout = httpx.Timeout(
            connect=config.connect_timeout,
            read=config.read_timeout,
            write=config.read_timeout,
            pool=config.read_timeout,
        )
        kwargs: dict = {
            "timeout": timeout,
            "headers": {"User-Agent": config.user_agent},
            "follow_redirects": True,
        }
        # httpx exposes ``proxy=`` in modern versions; older versions use
        # ``proxies=``. We set ``proxy`` and fall back if the install
        # happens to be old — Tor routing is worth the belt-and-braces.
        if config.tor_proxy_url:
            try:
                return httpx.AsyncClient(proxy=config.tor_proxy_url, **kwargs)
            except TypeError:
                return httpx.AsyncClient(proxies=config.tor_proxy_url, **kwargs)
        return httpx.AsyncClient(**kwargs)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AhmiaClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    # ─── Public search ───────────────────────────────────────────────────

    async def search(self, raw_query: str) -> AhmiaSearchReport:
        """Run a multi-page search and return a full report with provenance.

        Each page fetch goes through rate limit → circuit breaker → retry
        loop. Pages stop early if ``stop_on_all_duplicates`` triggers.
        """
        query = sanitize_query(
            raw_query,
            min_len=self._config.min_query_length,
            max_len=self._config.max_query_length,
        )

        started = asyncio.get_event_loop().time()
        report = AhmiaSearchReport(query=query)
        seen_urls: set[str] = set()

        for page in range(1, self._config.max_pages + 1):
            try:
                html = await self._fetch_page(query, page)
            except CircuitBreakerOpen as exc:
                logger.warning("[AHMIA] circuit open — aborting at page %d (%s)", page, exc)
                break
            except AhmiaUnavailable as exc:
                logger.warning("[AHMIA] page %d failed after retries: %s", page, exc)
                # Return what we already have — partial is better than none.
                break

            report.pages_fetched += 1
            page_results, dups = self._parse_page(html, page=page, seen_urls=seen_urls)
            report.results.extend(page_results)
            report.duplicates_dropped += dups

            if not page_results:
                # Page returned nothing new — Ahmia has no more results.
                break
            if self._config.stop_on_all_duplicates and dups > 0 and not page_results:
                break

        report.elapsed_seconds = asyncio.get_event_loop().time() - started
        return report

    # ─── Internals ───────────────────────────────────────────────────────

    async def _fetch_page(self, query: str, page: int) -> str:
        """Fetch a single Ahmia page with rate-limit + breaker + retry."""
        await self._bucket.acquire()

        async def _do() -> str:
            return await self._execute_with_retries(query, page)

        return await self._breaker.call(_do)

    async def _execute_with_retries(self, query: str, page: int) -> str:
        last_exc: Optional[Exception] = None
        params = {"q": query}
        # Ahmia uses ``&d=`` as the "page" argument on its classic search
        # template (``?q=…&d=N``). First page omits ``d``.
        if page > 1:
            params["d"] = str(page)

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._http.get(self._config.ahmia_base_url, params=params)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= self._config.max_retries:
                    raise AhmiaUnavailable(f"network error after {attempt + 1} attempts: {exc}") from exc
                await asyncio.sleep(self._backoff_delay(attempt))
                continue

            # 2xx — happy path.
            if 200 <= response.status_code < 300:
                return response.text

            # 429 / 5xx — retry with backoff.
            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request, response=response
                )
                if attempt >= self._config.max_retries:
                    raise AhmiaUnavailable(
                        f"Ahmia returned HTTP {response.status_code} after {attempt + 1} attempts"
                    ) from last_exc
                await asyncio.sleep(self._backoff_delay(attempt))
                continue

            # 4xx other than 429 — do not retry, propagate.
            raise AhmiaUnavailable(f"Ahmia returned HTTP {response.status_code}")

        # Should be unreachable — loop either returns or raises.
        raise AhmiaUnavailable(f"retry loop exhausted: {last_exc}")

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter, capped at ``retry_max_delay``."""
        base = self._config.retry_base_delay * (2 ** attempt)
        # Full jitter (AWS-style) — uniform in [0, base] — gives the best
        # collision avoidance when many workers retry at once.
        delay = random.uniform(0.0, base)
        return min(delay, self._config.retry_max_delay)

    def _parse_page(
        self, html: str, *, page: int, seen_urls: set[str]
    ) -> tuple[list[AhmiaResult], int]:
        """Parse Ahmia HTML into AhmiaResult list. Returns ``(results, dupes)``.

        ``seen_urls`` is mutated with every fresh URL. Duplicate URLs are
        dropped from the returned list and counted in ``dupes``.
        """
        soup = BeautifulSoup(html, "html.parser")
        out: list[AhmiaResult] = []
        dupes = 0
        fetched_at = datetime.now(timezone.utc).isoformat()

        for item in soup.select("li.result"):
            title_el = item.select_one("h4")
            url_el = item.select_one("p.onion-site, cite")
            desc_el = item.select_one("p.description")

            title = title_el.get_text(strip=True) if title_el else "(no title)"
            url = url_el.get_text(strip=True) if url_el else ""
            desc = desc_el.get_text(strip=True) if desc_el else ""

            if not url:
                continue
            if url in seen_urls:
                dupes += 1
                continue

            seen_urls.add(url)
            out.append(
                AhmiaResult(
                    title=title,
                    url=url,
                    description=desc,
                    fetched_at=fetched_at,
                    page=page,
                    via_tor=self._via_tor,
                )
            )

        return out, dupes


__all__ = [
    "AhmiaClient",
    "AhmiaResult",
    "AhmiaSearchReport",
    "AhmiaUnavailable",
    "InvalidQuery",
    "sanitize_query",
]
