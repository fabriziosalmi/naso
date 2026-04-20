"""Async token-bucket rate limiter.

Bounds the rate at which NASO fans out requests to external services
(Ahmia, Tor exits, etc.). Unlike a simple sleep-between-calls pattern, a
token bucket allows **bursts** (useful: the first operator probe of the
morning shouldn't be artificially throttled if the bucket is full) while
still enforcing a long-term ceiling.

Model:

    * The bucket holds at most ``burst`` tokens.
    * Tokens are added at a rate of ``tokens_per_second``, capped at
      ``burst``.
    * ``acquire(n)`` removes ``n`` tokens; if fewer are available, the
      call awaits until the deficit refills.
    * Fairness is FIFO via ``asyncio.Lock`` — two coroutines racing for
      the same bucket won't starve each other.

Usage::

    bucket = TokenBucket(tokens_per_second=2.0, burst=10)
    for query in queries:
        await bucket.acquire()
        response = await client.get(...)
"""
from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """FIFO-fair async token bucket."""

    __slots__ = ("_rate", "_capacity", "_tokens", "_last_refill", "_lock")

    def __init__(self, tokens_per_second: float, burst: int) -> None:
        if tokens_per_second <= 0:
            raise ValueError("tokens_per_second must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")
        self._rate = float(tokens_per_second)
        self._capacity = int(burst)
        # Start full — the first acquire can burst immediately. This matches
        # operator intuition: a fresh NASO deploy is not "rate-limited out
        # of the gate" on its first probe.
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        # asyncio.Lock is FIFO in CPython, which gives us fair ordering for
        # free. We rely on that for the "no starvation" property.
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> None:
        """Block until *tokens* are available, then consume them.

        Raises ``ValueError`` if ``tokens`` is non-positive or exceeds the
        bucket capacity (the latter would otherwise await forever).
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self._capacity:
            raise ValueError(
                f"requested {tokens} tokens exceeds capacity {self._capacity}"
            )

        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Compute the exact deficit and sleep for it. Always leaves
                # a tiny safety margin (1%) so we don't wake up one instant
                # too early and go round the loop uselessly.
                deficit = tokens - self._tokens
                wait = (deficit / self._rate) * 1.01
                await asyncio.sleep(wait)

    @property
    def available_tokens(self) -> float:
        """Snapshot of current token count. Diagnostic only; the value can
        change the instant it is read.
        """
        self._refill()
        return self._tokens


__all__ = ["TokenBucket"]
