"""The inference gate must actually serialize, and must fail the right way.

The deployment can throw at least five concurrent completions at the one
LM Studio instance on the operator's machine (4 Celery pipeline processes
plus a co-analyst chat), and enough parallel completions exhaust the
host's memory — the machine reboots, not just the requests. The gate in
``shared.utils.ai_gate`` is the fix: one inference in flight system-wide.

These tests drive the gate against an in-memory lock that enforces real
mutual exclusion, so they pin the contract rather than Redis itself:
  * two gated bodies never overlap,
  * the lock is HELD inside the body and released after, even when the
    body raises — and even when the body is cancelled from an anyio
    cancel scope, which is what a Starlette SSE client disconnect does
    (level-triggered: every await re-raises, so an unshielded release
    would never run and the gate would wedge for its full TTL),
  * an exhausted acquire budget raises AIGateTimeout,
  * an unreachable Redis AND a malformed REDIS_HOST both fail OPEN (dev
    boxes and CI have no Redis; a cache misconfiguration must degrade to
    "unprotected", never to "AI is down").

They patch ``ai_gate._redis_from_url`` — a seam owned by the module —
rather than ``redis.asyncio.from_url``, which is a process-wide global
shared with jwt_blacklist and the rate limiter.
"""

import asyncio

import anyio
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

import shared.utils.ai_gate as ai_gate
from shared.utils.ai_gate import AIGateTimeout, ai_inference_gate


class _FakeLock:
    """Mutual exclusion with the slice of redis.asyncio.lock.Lock we use."""

    def __init__(self, backend):
        self._backend = backend

    async def acquire(self):
        # Bounded: a gate that never releases must FAIL the suite (acquire
        # returns False → AIGateTimeout), not hang CI until the job timeout.
        for _ in range(2000):
            if self._backend["holder"] is None:
                self._backend["holder"] = self
                return True
            await asyncio.sleep(0.001)
        return False

    async def release(self):
        if self._backend["holder"] is not self:
            # Mirrors redis-py: releasing an unowned lock raises. The gate
            # must swallow this (it deliberately releases the candidate even
            # when acquire was cancelled mid-flight).
            from redis.exceptions import LockError

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
    monkeypatch.setattr(ai_gate, "_redis_from_url", lambda *_a, **_k: _FakeRedis(backend))
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
async def test_lock_is_held_inside_and_released_when_the_body_raises(gate_backend):
    with pytest.raises(RuntimeError):
        async with ai_inference_gate():
            # Held HERE — without this assert, "released after" would also
            # pass for a gate that never acquired anything at all.
            assert gate_backend["holder"] is not None
            raise RuntimeError("inference blew up")
    assert gate_backend["holder"] is None


@pytest.mark.asyncio
async def test_release_runs_even_under_anyio_cancel_scope(gate_backend):
    """A chat client disconnect must free the gate, not wedge it for the TTL.

    Starlette cancels the SSE generator through an anyio cancel scope, which
    is level-triggered: every await in the cancelled task re-raises. The
    gate's cleanup therefore runs as a shielded task; this test cancels a
    gated body exactly that way and asserts the lock is freed.
    """
    started = asyncio.Event()

    async def gated_body():
        async with ai_inference_gate():
            started.set()
            await asyncio.sleep(30)

    async with anyio.create_task_group() as tg:
        tg.start_soon(gated_body)
        await started.wait()
        assert gate_backend["holder"] is not None
        tg.cancel_scope.cancel()

    # The shielded cleanup finishes on this loop within a few ticks.
    for _ in range(100):
        if gate_backend["holder"] is None:
            break
        await asyncio.sleep(0.01)
    assert gate_backend["holder"] is None


@pytest.mark.asyncio
async def test_exhausted_acquire_budget_raises_gate_timeout(monkeypatch):
    class _BusyLock:
        async def acquire(self):
            return False  # what redis-py returns when blocking_timeout expires

        async def release(self):
            # The gate releases the candidate defensively even when acquire
            # said no (covers a cancel landing after SET NX but before
            # acquire returned); with redis-py this raises LockError, which
            # the cleanup swallows. Tolerate it silently here too.
            return None

    monkeypatch.setattr(ai_gate, "_redis_from_url", lambda *_a, **_k: _FakeRedis({}, lock_cls=lambda _b: _BusyLock()))
    with pytest.raises(AIGateTimeout):
        async with ai_inference_gate():
            raise AssertionError("body must not run without the lock")


@pytest.mark.asyncio
async def test_unreachable_redis_fails_open(monkeypatch):
    class _DeadLock:
        async def acquire(self):
            raise RedisConnectionError("connection refused")

    monkeypatch.setattr(ai_gate, "_redis_from_url", lambda *_a, **_k: _FakeRedis({}, lock_cls=lambda _b: _DeadLock()))
    ran = False
    async with ai_inference_gate():
        ran = True
    assert ran is True


@pytest.mark.asyncio
async def test_malformed_redis_url_fails_open(monkeypatch):
    """redis.from_url raises ValueError (not RedisError) for a scheme-less
    REDIS_HOST like 'naso-cache:6379'. A cache misconfiguration must degrade
    to unserialized inference, never take every AI feature down."""

    def _boom(*_a, **_k):
        raise ValueError("Redis URL must specify one of the following schemes")

    monkeypatch.setattr(ai_gate, "_redis_from_url", _boom)
    ran = False
    async with ai_inference_gate():
        ran = True
    assert ran is True
