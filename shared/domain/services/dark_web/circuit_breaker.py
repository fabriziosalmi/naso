"""Circuit breaker for the Ahmia / Tor fan-out.

Classic three-state machine:

    * **closed**  — requests flow normally; consecutive failures are
      counted and, on reaching ``failure_threshold``, the breaker trips to
      **open**.
    * **open**    — requests short-circuit with
      :class:`CircuitBreakerOpen` until ``recovery_timeout`` has passed
      since the last failure. At that point the breaker moves to
      **half-open**.
    * **half-open** — exactly ONE probe request is allowed through. If it
      succeeds the breaker closes; if it fails the breaker re-opens and
      the timer restarts.

This implementation is async-safe under ``asyncio.gather`` — state
transitions are guarded by an ``asyncio.Lock`` so concurrent callers cannot
both observe the breaker as closed and both try to probe.

The separate existing ``shared/utils/circuit_breaker.py`` is kept for its
Elasticsearch / MinIO instances; this one is scoped to dark-web traffic so
Tor cluster health does not contaminate the ES breaker and vice versa.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    """Raised when a request is rejected because the breaker is open."""


class _State(StrEnum):
    # StrEnum rather than (str, Enum): the two differ in __str__ -- the old form
    # renders as "_State.OPEN", StrEnum as "open". Safe here because nothing
    # interpolates a member. Every comparison in this file is `is`, and the one
    # value that escapes the class is `.value` via the `state` property, which
    # is the same string under either base.
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Async circuit breaker for dark-web egress calls."""

    __slots__ = (
        "_failure_threshold",
        "_recovery_timeout",
        "_state",
        "_failure_count",
        "_opened_at",
        "_lock",
        "_half_open_pending",
    )

    def __init__(self, *, failure_threshold: int, recovery_timeout: float) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        self._failure_threshold = int(failure_threshold)
        self._recovery_timeout = float(recovery_timeout)
        self._state = _State.CLOSED
        self._failure_count = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()
        # Ensures only one probe crosses a half-open gate.
        self._half_open_pending = False

    @property
    def state(self) -> str:
        return self._state.value

    def _maybe_move_to_half_open(self) -> None:
        if self._state is _State.OPEN and (time.monotonic() - self._opened_at) >= self._recovery_timeout:
            self._state = _State.HALF_OPEN
            self._half_open_pending = False

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run *fn()* through the breaker.

        * Closed → run, record success/failure.
        * Open → raise :class:`CircuitBreakerOpen` immediately.
        * Half-open → allow one probe; others short-circuit.
        """
        async with self._lock:
            self._maybe_move_to_half_open()

            if self._state is _State.OPEN:
                raise CircuitBreakerOpen("circuit is open")

            if self._state is _State.HALF_OPEN:
                if self._half_open_pending:
                    # Someone else is already probing; refuse fast.
                    raise CircuitBreakerOpen("probe in flight")
                self._half_open_pending = True

        # Perform the call outside the lock so we don't serialize all
        # traffic behind a single mutex — only the state transitions need
        # exclusive access.
        try:
            result = await fn()
        except Exception:
            async with self._lock:
                self._record_failure()
            raise
        else:
            async with self._lock:
                self._record_success()
            return result

    def _record_success(self) -> None:
        self._failure_count = 0
        self._state = _State.CLOSED
        self._half_open_pending = False

    def _record_failure(self) -> None:
        self._failure_count += 1
        # Every failure during half-open re-opens the breaker outright.
        if self._state is _State.HALF_OPEN or self._failure_count >= self._failure_threshold:
            self._state = _State.OPEN
            self._opened_at = time.monotonic()
            self._half_open_pending = False


__all__ = ["CircuitBreaker", "CircuitBreakerOpen"]
