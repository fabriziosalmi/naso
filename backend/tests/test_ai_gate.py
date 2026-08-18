"""The inference gate must actually serialize, and must fail the right way.

The deployment can throw at least five concurrent completions at the one
LM Studio instance on the operator's machine (4 Celery pipeline processes
plus a co-analyst chat), and enough parallel completions exhaust the
host's memory — the machine reboots, not just the requests. The gate in
``shared.utils.ai_gate`` is the fix: one inference in flight system-wide.

These tests drive the gate against an in-memory lock that enforces real
mutual exclusion, so they pin the contract rather than Redis itself:
  * two gated bodies never overlap,
  * the lock is released even when the gated body raises,
  * an exhausted acquire budget raises AIGateTimeout,
  * an unreachable Redis fails OPEN (dev boxes and CI have no Redis, and
    a missing lock must degrade to "unprotected", never to "AI is down").
"""

import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import LockError

import shared.utils.ai_gate as ai_gate
from shared.utils.ai_gate import AIGateTimeout, ai_inference_gate


class _FakeLock:
    """Mutual exclusion with the slice of redis.asyncio.lock.Lock we use."""

    def __init__(self, backend):
        self._backend = backend

    async def acquire(self):
        while self._backend["holder"] is not None:
            await asyncio.sleep(0.001)
        self._backend["holder"] = self
        return True

    async def release(self):
        if self._backend["holder"] is not self:
            raise LockError("cannot release an unowned lock")
        self._backend["holder"] = None


class _FakeRedis:
    def __init__(self, backend, lock_cls=_FakeLock):
        self._backend = backend
        self._lock_cls = lock_cls

    def lock(self, *_args, **_kwargs):
        return self._lock_cls(self._backend)

    async def aclose(self):
        return None


@pytest.fixture
def gate_backend(monkeypatch):
    """Route the gate's Redis at a shared in-memory lock; return its state."""
    backend = {"holder": None}
    monkeypatch.setattr(ai_gate.redis, "from_url", lambda *_a, **_k: _FakeRedis(backend))
    return backend


@pytest.mark.asyncio
async def test_gated_bodies_never_overlap(gate_backend):
    in_flight = 0
    max_in_flight = 0

    async def gated_inference():
        nonlocal in_flight, max_in_flight
        async with ai_inference_gate():
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)  # long enough for the others to pile up
            in_flight -= 1

    await asyncio.gather(*(gated_inference() for _ in range(5)))
    assert max_in_flight == 1


@pytest.mark.asyncio
async def test_lock_is_released_when_the_body_raises(gate_backend):
    with pytest.raises(RuntimeError):
        async with ai_inference_gate():
            raise RuntimeError("inference blew up")
    assert gate_backend["holder"] is None


@pytest.mark.asyncio
async def test_exhausted_acquire_budget_raises_gate_timeout(monkeypatch):
    class _BusyLock:
        async def acquire(self):
            return False  # what redis-py returns when blocking_timeout expires

        async def release(self):
            raise AssertionError("never acquired, must never be released")

    monkeypatch.setattr(ai_gate.redis, "from_url", lambda *_a, **_k: _FakeRedis({}, lock_cls=lambda _b: _BusyLock()))
    with pytest.raises(AIGateTimeout):
        async with ai_inference_gate():
            raise AssertionError("body must not run without the lock")


@pytest.mark.asyncio
async def test_unreachable_redis_fails_open(monkeypatch):
    class _DeadLock:
        async def acquire(self):
            raise RedisConnectionError("connection refused")

    monkeypatch.setattr(ai_gate.redis, "from_url", lambda *_a, **_k: _FakeRedis({}, lock_cls=lambda _b: _DeadLock()))
    ran = False
    async with ai_inference_gate():
        ran = True
    assert ran is True
