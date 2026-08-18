"""Global one-at-a-time gate for local LLM inference.

NASO's AI features all talk to one LM Studio instance running on the
operator's own machine, and that machine is not a GPU cluster: the model
occupies most of its unified memory, and every *concurrent* completion
allocates its own KV cache and inference buffers on top. The deployment
can produce plenty of concurrency — worker-pipeline runs 4 Celery
processes whose triage calls all race, on top of however many co-analyst
chats are open — and enough simultaneous completions exhausts the host's
memory and takes the whole machine down, not just the requests.

So inference is serialized *system-wide*: every chat/completions call, in
any process or container, first takes this Redis-backed lock. One request
runs at a time; the rest wait their turn. The `/models` health probe does
not run inference and is deliberately not gated.

Failure modes, chosen deliberately:
  * Holder crashes (SIGKILL, power loss) → the lock's TTL frees the gate
    on its own instead of wedging AI forever.
  * Holder is *cancelled* (SSE client disconnect under anyio's
    level-triggered cancel scopes, where every await re-raises) → the
    release runs in a shielded task so the gate is freed immediately,
    not after the TTL.
  * A slow-but-alive holder cannot outlive the TTL either: httpx
    timeouts are per-phase, not wall-clock, so the gate itself bounds
    the body with ``asyncio.timeout`` just under the TTL. The double
    inference that a silently-expired lock would allow becomes a loud
    ``TimeoutError`` that both call sites already degrade on.
  * A caller queues past its acquire budget → ``AIGateTimeout``. Both
    call sites degrade gracefully (triage falls back to the YARA score;
    chat surfaces an SSE error event). The default budget lives in
    Settings; the triage worker passes a tighter one so gate wait plus
    its 90s HTTP timeout stays well inside Celery's 300s hard kill.
  * Redis unreachable or misconfigured → the gate fails OPEN with a
    warning. A missing lock protects nothing, but blocking every AI
    feature on the cache being up would be the worse failure — and it
    keeps dev setups and unit tests (no Redis) working unchanged. The
    client carries explicit socket timeouts so a black-holed Redis
    (paused container, dropped packets) fails open in seconds instead
    of hanging the hot path in TCP connect.

The Redis client is created and closed inside the context manager on
purpose: Celery tasks each run ``asyncio.new_event_loop()``, so a cached
module-level asyncio client would leak across event loops. One TCP
connect per inference request is noise next to the seconds-to-minutes the
inference itself takes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis
from redis.exceptions import LockNotOwnedError, RedisError

from shared.config import settings

logger = logging.getLogger("naso-ai")

AI_GATE_KEY = "ai:inference_gate"

_POLL_SECONDS = 0.5

# Test seam: unit tests patch this attribute instead of mutating the global
# redis.asyncio module (which would leak the patch into every other consumer
# sharing the process — jwt_blacklist, the rate limiter).
_redis_from_url = redis.from_url


async def _release_and_close(lock, client) -> None:
    """Free the gate and drop the connection; never raise."""
    try:
        if lock is not None:
            await lock.release()
    except LockNotOwnedError:
        # The TTL expired under a live holder: serialization was voided
        # for this request. Loud, because the whole point of the gate is
        # that this never happens silently.
        logger.warning("AI inference gate TTL expired under a live holder — hold TTL is too low")
    except Exception:
        # Releasing a never-acquired candidate raises LockError; a dropped
        # connection raises RedisError/OSError. None of them may mask the
        # body's own outcome.
        pass
    with contextlib.suppress(Exception):
        await client.aclose()


class AIGateTimeout(Exception):
    """The local LLM stayed busy for the whole acquire budget."""


@contextlib.asynccontextmanager
async def ai_inference_gate(acquire_timeout: float | None = None) -> AsyncGenerator[None, None]:
    """Admit exactly one local-LLM inference at a time, system-wide.

    ``acquire_timeout`` overrides the Settings default for call sites with a
    tighter deadline (Celery task limits, interactive chat).
    """
    hold_ttl = settings.AI_GATE_HOLD_TTL_SECONDS
    budget = acquire_timeout if acquire_timeout is not None else settings.AI_GATE_ACQUIRE_TIMEOUT_SECONDS
    client = None
    lock = None
    candidate = None
    try:
        try:
            client = _redis_from_url(
                settings.REDIS_HOST,
                socket_connect_timeout=2.0,
                socket_timeout=5.0,
            )
            candidate = client.lock(
                AI_GATE_KEY,
                timeout=hold_ttl,
                sleep=_POLL_SECONDS,
                blocking_timeout=budget,
            )
            if await candidate.acquire():
                lock = candidate
            else:
                raise AIGateTimeout(f"local LLM busy — gave up after {budget:.0f}s in the inference queue")
        except (RedisError, OSError, ValueError) as exc:
            # ValueError covers a malformed REDIS_HOST (redis.from_url raises
            # it, not a RedisError): a cache misconfiguration must degrade to
            # "unserialized", never to "AI is down".
            logger.warning("AI inference gate unavailable (%s) — proceeding ungated", exc)
        # Bound the holder's WALL CLOCK just under the lock TTL. httpx
        # timeouts are per-phase (connect/read/write each get the full
        # budget), so without this a slow-but-alive completion could outlive
        # the TTL and let a second inference start concurrently.
        async with asyncio.timeout(max(hold_ttl - 5.0, 1.0)):
            yield
    finally:
        if client is not None:
            # Shielded: on SSE client disconnect anyio cancels the task with a
            # level-triggered scope where every await re-raises CancelledError,
            # so an inline `await lock.release()` would never complete and the
            # gate would stay wedged for the full TTL. The shielded task keeps
            # running on the loop and frees it immediately. `candidate` (not
            # `lock`) so a cancel landing inside acquire() — after the SET NX
            # succeeded but before acquire returned — is released too; an
            # unlocked candidate raises LockError, which _release_and_close
            # swallows.
            cleanup = asyncio.ensure_future(_release_and_close(candidate if lock is None else lock, client))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                # We are being cancelled; cleanup continues in the background.
                raise
