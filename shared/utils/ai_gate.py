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
  * Holder crashes → the lock's TTL (set above the longest client
    timeout) frees the gate on its own instead of wedging AI forever.
  * A caller waits longer than ``_ACQUIRE_TIMEOUT_SECONDS`` →
    ``AIGateTimeout``. Both call sites already degrade gracefully on
    exception (triage falls back to the YARA score; chat surfaces an SSE
    error event), and the ceiling stays under Celery's 300s hard task
    limit so a queued triage degrades instead of being SIGKILLed.
  * Redis unreachable → the gate fails OPEN with a warning. A missing
    lock protects nothing, but blocking every AI feature on the cache
    being up would be the worse failure — and it keeps dev setups and
    unit tests (no Redis) working unchanged.

The Redis client is created and closed inside the context manager on
purpose: Celery tasks each run ``asyncio.new_event_loop()``, so a cached
module-level asyncio client would leak across event loops. One TCP
connect per inference request is noise next to the seconds-to-minutes the
inference itself takes.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis
from redis.exceptions import LockError, RedisError

from shared.config import settings

logger = logging.getLogger("naso-ai")

AI_GATE_KEY = "ai:inference_gate"

# How long one holder may keep the gate. Above the longest client timeout
# (chat 120s, triage 90s) so the TTL only ever fires for a crashed holder,
# never a slow-but-alive one.
_HOLD_TTL_SECONDS = 150.0

# How long a caller queues for its turn before giving up with AIGateTimeout.
# Kept under Celery's task_time_limit (300s): degrade, don't get SIGKILLed.
_ACQUIRE_TIMEOUT_SECONDS = 180.0

_POLL_SECONDS = 0.5


class AIGateTimeout(Exception):
    """The local LLM stayed busy for the whole acquire budget."""


@contextlib.asynccontextmanager
async def ai_inference_gate() -> AsyncGenerator[None, None]:
    """Admit exactly one local-LLM inference at a time, system-wide."""
    client = redis.from_url(settings.REDIS_HOST)
    lock = None
    try:
        try:
            candidate = client.lock(
                AI_GATE_KEY,
                timeout=_HOLD_TTL_SECONDS,
                sleep=_POLL_SECONDS,
                blocking_timeout=_ACQUIRE_TIMEOUT_SECONDS,
            )
            if await candidate.acquire():
                lock = candidate
            else:
                raise AIGateTimeout(
                    f"local LLM busy — gave up after {_ACQUIRE_TIMEOUT_SECONDS:.0f}s in the inference queue"
                )
        except RedisError as exc:
            logger.warning("AI inference gate unavailable (%s) — proceeding ungated", exc)
        yield
    finally:
        if lock is not None:
            with contextlib.suppress(LockError, RedisError):
                await lock.release()
        with contextlib.suppress(Exception):
            await client.aclose()
