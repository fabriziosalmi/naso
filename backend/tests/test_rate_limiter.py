"""Token bucket semantics — burst, refill, fairness, overcommit guards."""

from __future__ import annotations

import asyncio
import time

import pytest

from shared.domain.services.dark_web.rate_limiter import TokenBucket

# Async marker is applied per-test rather than at module scope so the
# handful of synchronous construction tests below do not trigger pytest's
# "marked asyncio but not async" warnings.


class TestConstruction:
    def test_rejects_non_positive_rate(self):
        with pytest.raises(ValueError):
            TokenBucket(tokens_per_second=0, burst=5)
        with pytest.raises(ValueError):
            TokenBucket(tokens_per_second=-1, burst=5)

    def test_rejects_non_positive_burst(self):
        with pytest.raises(ValueError):
            TokenBucket(tokens_per_second=1, burst=0)


@pytest.mark.asyncio
class TestBurst:
    async def test_burst_is_immediate(self):
        bucket = TokenBucket(tokens_per_second=1.0, burst=10)
        started = time.monotonic()
        # All 10 tokens should be available from start — no sleeps expected.
        for _ in range(10):
            await bucket.acquire()
        elapsed = time.monotonic() - started
        # Some scheduling noise is unavoidable, but 10 instant acquires
        # must be sub-second.
        assert elapsed < 0.2, f"burst should be immediate, took {elapsed:.2f}s"


@pytest.mark.asyncio
class TestSteadyStateRate:
    async def test_throttles_after_burst(self):
        bucket = TokenBucket(tokens_per_second=10.0, burst=2)
        # Drain the bucket with a burst.
        await bucket.acquire()
        await bucket.acquire()

        started = time.monotonic()
        # Third acquire must wait ~0.1s to refill one token (10 tps).
        await bucket.acquire()
        elapsed = time.monotonic() - started
        # Generous window for CI jitter but enough to prove it blocked.
        assert 0.05 < elapsed < 0.3, f"expected ~0.1s wait, got {elapsed:.3f}s"


@pytest.mark.asyncio
class TestOvercommit:
    async def test_rejects_request_exceeding_capacity(self):
        bucket = TokenBucket(tokens_per_second=1.0, burst=3)
        with pytest.raises(ValueError):
            await bucket.acquire(tokens=4)

    async def test_rejects_non_positive_token_count(self):
        bucket = TokenBucket(tokens_per_second=1.0, burst=3)
        with pytest.raises(ValueError):
            await bucket.acquire(tokens=0)


@pytest.mark.asyncio
class TestFairness:
    async def test_concurrent_acquires_complete_in_order(self):
        """Two coroutines racing for the bucket both finish in FIFO order."""
        bucket = TokenBucket(tokens_per_second=20.0, burst=1)
        await bucket.acquire()  # drain

        order: list[int] = []

        async def task(idx: int) -> None:
            await bucket.acquire()
            order.append(idx)

        # Schedule in order so FIFO is unambiguous.
        t1 = asyncio.create_task(task(1))
        await asyncio.sleep(0)
        t2 = asyncio.create_task(task(2))
        await asyncio.gather(t1, t2)
        assert order == [1, 2]
