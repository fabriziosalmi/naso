"""Legacy Dark Web search entrypoint — thin façade over :mod:`dark_web`.

The original implementation was a single ~50-line file that opened a new
``httpx.AsyncClient`` per call, hit Ahmia over clearnet with no retry /
backoff / pagination / rate limiting / circuit breaker, and returned
whatever came back. Every failure mode — Ahmia 5xx, timeout, partial page,
captcha, duplicate results — was silently ignored.

The Tor/Ahmia hardening round introduces a proper pipeline under
:mod:`shared.domain.services.dark_web`. This module keeps the legacy
``DarkWebSearchService.search_onion_links()`` classmethod working (so
existing callers — ``/leaks/recon/darkweb`` endpoint, AI tool
``dark_web_probe``, MCP server — do not need to change) by delegating to
an :class:`AhmiaClient` instance.

The returned list keeps the same ``{"title", "url", "description"}``
shape so the frontend UI continues to render. Additional provenance
fields (``fetched_at``, ``page``, ``via_tor``, ``source``) are appended
but optional — callers that need them can ask; old callers simply ignore.
"""

from __future__ import annotations

import logging

from .dark_web.ahmia_client import (
    AhmiaClient,
    AhmiaSearchReport,
    AhmiaUnavailable,
    InvalidQuery,
)

logger = logging.getLogger("naso-darkweb-search")


class DarkWebSearchService:
    """Legacy-compatible façade. New code should use :class:`AhmiaClient`
    directly for access to the full :class:`AhmiaSearchReport` object
    (pages fetched, duplicates dropped, elapsed time).
    """

    # Preserved for anything that imported the class attribute. The real
    # URL lives in ``DarkWebConfig.ahmia_base_url``.
    AHMIA_URL = "https://ahmia.fi/search/"

    @classmethod
    async def search_onion_links(cls, query: str) -> list[dict]:
        """Run an Ahmia search and return the result list in the legacy
        shape. Raises ``ValueError`` on sanitization failure (matching the
        legacy contract) and on unrecoverable Ahmia unavailability.

        The underlying :class:`AhmiaClient` is instantiated per call here;
        long-running callers (e.g. the Celery worker) should move to
        constructing a single ``AhmiaClient`` and reusing it across probes
        — connection pool wins.
        """
        try:
            async with AhmiaClient() as client:
                report = await client.search(query)
        except InvalidQuery as exc:
            # Translate to ValueError to preserve the legacy contract.
            raise ValueError(f"Dark Web search failed: {exc}") from exc
        except AhmiaUnavailable as exc:
            raise ValueError(f"Dark Web node unreachable: {exc}") from exc

        logger.info(
            "[DARK SEARCH] query '%s' → %d results across %d page(s) (%d duplicates dropped)",
            report.query,
            len(report.results),
            report.pages_fetched,
            report.duplicates_dropped,
        )

        # Return the legacy dict shape; callers who want provenance fields
        # can inspect them — they are present but unadvertised.
        return [r.as_dict() for r in report.results]

    @classmethod
    async def search_with_report(cls, query: str) -> AhmiaSearchReport:
        """Same search as :meth:`search_onion_links` but returns the full
        :class:`AhmiaSearchReport` — including ``cached``, ``pages_fetched``,
        ``duplicates_dropped``, ``rotation_report``. Use this from code
        paths that can surface that metadata to the UI (the DarkRecon page
        renders a "from cache" badge and a Tor rotation status chip).
        """
        try:
            async with AhmiaClient() as client:
                return await client.search(query)
        except InvalidQuery as exc:
            raise ValueError(f"Dark Web search failed: {exc}") from exc
        except AhmiaUnavailable as exc:
            raise ValueError(f"Dark Web node unreachable: {exc}") from exc
