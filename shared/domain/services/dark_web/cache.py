"""Result cache for the Ahmia pipeline.

An identical operator probe within a few minutes is a very common UX
pattern — typo correction, side-by-side comparison between two analyst
sessions, the DarkRecon page refresh. Without caching every one of those
is a fresh multi-page Ahmia round-trip routed over Tor, which is slow
*and* makes us a loud neighbour on a shared community resource.

Design
------
* ``AhmiaCache`` is a minimal async protocol (get + set). Production can
  plug in a Redis-backed implementation without touching ``AhmiaClient``.
* :class:`InMemoryTTLCache` is the default implementation — zero
  external dependencies, per-process, good enough for a single-worker
  dev setup and for the test suite. Eviction is LRU when
  ``max_size`` is exceeded.
* Keys are caller-supplied so the cache does not need to know about
  tenants; Ahmia output is the same for every tenant so we key purely
  on the sanitized query string.
* Values are kept as ``AhmiaSearchReport`` objects — we do not touch the
  provenance timestamps, so an operator seeing a cached result can still
  tell *when* it was really fetched.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Protocol, TypeVar

T = TypeVar("T")


class AhmiaCache(Protocol[T]):
    """Minimal async cache interface used by :class:`AhmiaClient`."""

    async def get(self, key: str) -> T | None: ...

    async def set(self, key: str, value: T, *, ttl_seconds: int) -> None: ...


class InMemoryTTLCache:
    """LRU + TTL cache, process-local, async-safe via ``asyncio.Lock``.

    Scaling note: for a multi-worker deployment, swap in a Redis-backed
    implementation of the same protocol. The in-memory cache suffices for
    the typical single-worker dev setup and for the test suite (zero
    external dependencies).
    """

    __slots__ = ("_store", "_max_size", "_lock")

    def __init__(self, max_size: int = 1024) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        # OrderedDict[key, (value, expires_at_monotonic)] — popitem(last=False)
        # gives us O(1) LRU eviction; move_to_end on access keeps recency.
        self._store: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._max_size = int(max_size)
        # Single lock covers both get (for move_to_end) and set (eviction).
        # Cheap compared to the cost of a cache miss that triggers a Tor
        # round-trip.
        self._lock = asyncio.Lock()

    async def get(self, key: str):
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at < time.monotonic():
                # Expired — drop and report miss.
                self._store.pop(key, None)
                return None
            # Touch for LRU.
            self._store.move_to_end(key)
            return value

    async def set(self, key: str, value, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            # TTL of 0 or less effectively disables caching for this entry.
            return
        expires_at = time.monotonic() + ttl_seconds
        async with self._lock:
            # Insert at the end (most recent).
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expires_at)
            # LRU eviction.
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


__all__ = ["AhmiaCache", "InMemoryTTLCache"]
