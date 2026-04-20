"""Centralized dark-web search configuration.

Every knob that affects how NASO talks to Ahmia / the Tor cluster lives
here, in a single ``dataclass`` so:

    * Tests can build a tight config (small timeouts, zero retries, tiny
      rate limit) without monkey-patching module globals.
    * Production swaps a single import site — ``DarkWebConfig.from_env()``
      reads the standard env vars and returns a frozen instance.
    * Accidental drift is caught at boot, not at first failed request.

All durations are seconds, all sizes are counts. Defaults are tuned for
conservative clearnet Ahmia queries; production should enable
``tor_proxy_url`` so the traffic is routed through the local Tor cluster.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DarkWebConfig:
    """Read-only configuration for the Ahmia / Tor pipeline."""

    # ─── Endpoint ────────────────────────────────────────────────────────
    ahmia_base_url: str = "https://ahmia.fi/search/"

    # ─── Pagination ──────────────────────────────────────────────────────
    # Ahmia serves ~25 results per page; 5 pages = ~125 hits, which is
    # plenty for operator-driven triage without hammering the service.
    max_pages: int = 5

    # Stop paging when a page returns only URLs we have already seen —
    # prevents infinite loops if Ahmia's pagination ever degrades into
    # returning the same page for different ``&d=`` values.
    stop_on_all_duplicates: bool = True

    # ─── Timeouts (seconds) ──────────────────────────────────────────────
    connect_timeout: float = 10.0
    read_timeout: float = 30.0

    # ─── Retry policy ────────────────────────────────────────────────────
    max_retries: int = 3
    retry_base_delay: float = 0.5
    retry_max_delay: float = 8.0

    # ─── Circuit breaker ─────────────────────────────────────────────────
    # Trip after this many consecutive failures and refuse further calls
    # until ``recovery_timeout`` has elapsed since the last failure.
    failure_threshold: int = 5
    recovery_timeout: float = 60.0

    # ─── Rate limiting (token bucket) ────────────────────────────────────
    # Default: 2 requests/sec steady-state with bursts up to 10. Ahmia is
    # a shared community resource — we do not want to be the loud neighbour.
    rate_tokens_per_second: float = 2.0
    rate_burst: int = 10

    # ─── Tor routing (opt-in) ────────────────────────────────────────────
    # e.g. "socks5://naso-tor-cluster:8118" to route Ahmia queries through
    # the local Tor cluster. None = clearnet (default for tests).
    tor_proxy_url: str | None = None

    # Tor ControlPort for NEWNYM signal (circuit rotation). Empty list
    # disables rotation; otherwise every host receives the signal in
    # parallel before a probe. HAProxy balances SOCKS round-robin across
    # the cluster, so rotating only one instance is a no-op whenever the
    # next request lands on an un-rotated peer — broadcast is the only
    # correct policy.
    tor_control_hosts: tuple[str, ...] = ()
    tor_control_port: int = 9051

    # ``HashedControlPassword`` plaintext counterpart; set to ``None`` if
    # your torrc has no password (not recommended outside dev).
    tor_control_password: str | None = None

    # Issue a NEWNYM before each top-level query when True. Requires
    # ``tor_control_hosts`` to be non-empty.
    rotate_circuit_per_query: bool = False

    # ─── Result cache ────────────────────────────────────────────────────
    # Seconds a successful search report lives in cache before it expires.
    # 0 disables caching entirely. Five minutes is a good default: long
    # enough to save operators from repeated typo corrections, short
    # enough that fresh intel wins over stale.
    cache_ttl_seconds: int = 300

    # Hard ceiling on the number of distinct queries held in memory.
    # Prevents a pathological workload (e.g. a scripted fuzzer) from
    # chewing unbounded heap.
    cache_max_size: int = 1024

    # ─── Query sanitization ──────────────────────────────────────────────
    # Queries longer than this are rejected up front — Ahmia truncates
    # silently, which makes debugging hard.
    max_query_length: int = 256

    # Minimum length to guard against accidental empty-string probes that
    # would return Ahmia's landing page instead of a result set.
    min_query_length: int = 2

    # ─── User agent ──────────────────────────────────────────────────────
    # Identifies our traffic honestly. Ahmia staff have asked operators to
    # set a recognisable UA so they can triage abuse reports.
    user_agent: str = "NASO-Forensic/2.0 (+https://github.com/naso)"

    # ─── Construction helpers ────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "DarkWebConfig":
        """Load config from the standard ``NASO_DARKWEB_*`` env vars.

        Unrecognised vars are ignored; missing vars fall back to the class
        defaults. No env var may widen a safety bound (e.g. you cannot set
        ``max_pages`` above 20 or ``retry_max_delay`` above 60s).
        """

        def _float(name: str, default: float) -> float:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return float(raw)
            except ValueError:
                return default

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        def _bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        max_pages = min(_int("NASO_DARKWEB_MAX_PAGES", cls.max_pages), 20)

        # Comma-separated list: ``naso-tor-1,naso-tor-2,naso-tor-3,...``
        raw_hosts = os.getenv("NASO_DARKWEB_TOR_CONTROL_HOSTS", "")
        hosts_tuple = tuple(h.strip() for h in raw_hosts.split(",") if h.strip())

        return cls(
            ahmia_base_url=os.getenv("NASO_DARKWEB_AHMIA_URL", cls.ahmia_base_url),
            max_pages=max_pages,
            connect_timeout=_float("NASO_DARKWEB_CONNECT_TIMEOUT", cls.connect_timeout),
            read_timeout=_float("NASO_DARKWEB_READ_TIMEOUT", cls.read_timeout),
            max_retries=min(_int("NASO_DARKWEB_MAX_RETRIES", cls.max_retries), 10),
            retry_base_delay=_float("NASO_DARKWEB_RETRY_BASE", cls.retry_base_delay),
            retry_max_delay=min(_float("NASO_DARKWEB_RETRY_MAX", cls.retry_max_delay), 60.0),
            failure_threshold=_int("NASO_DARKWEB_FAILURE_THRESHOLD", cls.failure_threshold),
            recovery_timeout=_float("NASO_DARKWEB_RECOVERY_TIMEOUT", cls.recovery_timeout),
            rate_tokens_per_second=_float("NASO_DARKWEB_RATE_TPS", cls.rate_tokens_per_second),
            rate_burst=_int("NASO_DARKWEB_RATE_BURST", cls.rate_burst),
            tor_proxy_url=os.getenv("NASO_DARKWEB_TOR_PROXY") or None,
            tor_control_hosts=hosts_tuple,
            tor_control_port=_int("NASO_DARKWEB_TOR_CONTROL_PORT", cls.tor_control_port),
            tor_control_password=os.getenv("NASO_DARKWEB_TOR_CONTROL_PASSWORD") or None,
            rotate_circuit_per_query=_bool(
                "NASO_DARKWEB_ROTATE_CIRCUIT", cls.rotate_circuit_per_query
            ),
            cache_ttl_seconds=_int("NASO_DARKWEB_CACHE_TTL", cls.cache_ttl_seconds),
            cache_max_size=_int("NASO_DARKWEB_CACHE_MAX_SIZE", cls.cache_max_size),
            max_query_length=_int("NASO_DARKWEB_MAX_QUERY_LEN", cls.max_query_length),
            user_agent=os.getenv("NASO_DARKWEB_USER_AGENT", cls.user_agent),
        )


# Default instance used by the service unless a caller injects its own.
DEFAULT_CONFIG = DarkWebConfig()


__all__ = ["DarkWebConfig", "DEFAULT_CONFIG"]
