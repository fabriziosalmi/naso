"""InMemoryTTLCache semantics.

Contracts exercised:
    * Hit / miss / overwrite.
    * TTL expiry (monotonic clock, not wall clock).
    * LRU eviction when ``max_size`` is exceeded — oldest is dropped,
      a touched entry survives.
    * ``ttl_seconds <= 0`` is a no-op set (cache is bypassed).
    * Concurrent set under ``asyncio.Lock`` does not corrupt state.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from shared.domain.services.dark_web.cache import InMemoryTTLCache

# Async marker applied per-class so the sync construction tests don't warn.


@pytest.mark.asyncio
class TestBasicGetSet:
    async def test_miss_returns_none(self):
        cache = InMemoryTTLCache()
        assert await cache.get("nope") is None

    async def test_set_then_get_returns_value(self):
        cache = InMemoryTTLCache()
        await cache.set("k", {"data": 1}, ttl_seconds=10)
        assert await cache.get("k") == {"data": 1}

    async def test_overwrite_updates_value(self):
        cache = InMemoryTTLCache()
        await cache.set("k", "old", ttl_seconds=10)
        await cache.set("k", "new", ttl_seconds=10)
        assert await cache.get("k") == "new"


@pytest.mark.asyncio
class TestTTLExpiry:
    async def test_entry_expires_after_ttl(self, monkeypatch):
        cache = InMemoryTTLCache()

        # Freeze + advance the monotonic clock used inside the cache.
        class Clock:
            t = 0.0

        monkeypatch.setattr("shared.domain.services.dark_web.cache.time.monotonic", lambda: Clock.t)

        await cache.set("k", "v", ttl_seconds=5)
        Clock.t = 2.0
        assert await cache.get("k") == "v"
        Clock.t = 5.1
        assert await cache.get("k") is None

    async def test_zero_ttl_is_noop(self):
        cache = InMemoryTTLCache()
        await cache.set("k", "v", ttl_seconds=0)
        assert await cache.get("k") is None

    async def test_negative_ttl_is_noop(self):
        cache = InMemoryTTLCache()
        await cache.set("k", "v", ttl_seconds=-5)
        assert await cache.get("k") is None


@pytest.mark.asyncio
class TestLRUEviction:
    async def test_oldest_entry_dropped_when_full(self):
        cache = InMemoryTTLCache(max_size=3)
        await cache.set("a", 1, ttl_seconds=10)
        await cache.set("b", 2, ttl_seconds=10)
        await cache.set("c", 3, ttl_seconds=10)
        # Overflow — "a" should be evicted as oldest.
        await cache.set("d", 4, ttl_seconds=10)
        assert await cache.get("a") is None
        assert await cache.get("b") == 2
        assert await cache.get("c") == 3
        assert await cache.get("d") == 4

    async def test_touched_entry_survives_eviction(self):
        cache = InMemoryTTLCache(max_size=3)
        await cache.set("a", 1, ttl_seconds=10)
        await cache.set("b", 2, ttl_seconds=10)
        await cache.set("c", 3, ttl_seconds=10)
        # Touch "a" — it moves to the most-recently-used position.
        assert await cache.get("a") == 1
        # Now "b" is the oldest.
        await cache.set("d", 4, ttl_seconds=10)
        assert await cache.get("a") == 1
        assert await cache.get("b") is None
        assert await cache.get("c") == 3
        assert await cache.get("d") == 4


class TestConstruction:
    def test_rejects_non_positive_max_size(self):
        with pytest.raises(ValueError):
            InMemoryTTLCache(max_size=0)
        with pytest.raises(ValueError):
            InMemoryTTLCache(max_size=-1)


@pytest.mark.asyncio
class TestConcurrentWrites:
    async def test_gather_of_many_sets_does_not_corrupt(self):
        cache = InMemoryTTLCache(max_size=500)

        async def writer(i):
            await cache.set(f"k{i}", i, ttl_seconds=60)

        await asyncio.gather(*(writer(i) for i in range(200)))
        assert cache.size == 200
        # Random sample verifies no torn values.
        assert await cache.get("k42") == 42
        assert await cache.get("k199") == 199


@pytest.mark.asyncio
class TestClear:
    async def test_clear_empties_cache(self):
        cache = InMemoryTTLCache()
        await cache.set("k", "v", ttl_seconds=10)
        await cache.clear()
        assert cache.size == 0
        assert await cache.get("k") is None
