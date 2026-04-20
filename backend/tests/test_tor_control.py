"""NEWNYM broadcast contract tests.

``rotate_circuits`` is tested in isolation with an injected ``rotator`` so
no real Tor controller, no stem dependency, no network. Contract:

    * Calls the rotator once per host with the configured port/password.
    * Runs rotators in parallel (asyncio.gather).
    * Swallows per-host errors — degraded NEWNYM never aborts a search.
    * Sleeps ``settle_seconds`` after a successful broadcast.
    * Returns a per-host status dict.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from shared.domain.services.dark_web.tor_control import rotate_circuits

pytestmark = pytest.mark.asyncio


class TestBroadcast:
    async def test_calls_rotator_once_per_host(self):
        calls: list[tuple[str, int, str | None]] = []

        def fake(host, port, password):
            calls.append((host, port, password))

        result = await rotate_circuits(
            ["a", "b", "c"], port=9051, password="pw", rotator=fake, settle_seconds=0
        )
        assert result == {"a": "ok", "b": "ok", "c": "ok"}
        assert {c[0] for c in calls} == {"a", "b", "c"}
        # Every call used the same (port, password).
        assert all(c[1] == 9051 and c[2] == "pw" for c in calls)

    async def test_empty_hosts_is_noop(self):
        calls = []

        def fake(host, port, password):
            calls.append(host)

        result = await rotate_circuits([], port=9051, password=None, rotator=fake)
        assert result == {}
        assert calls == []


class TestErrorIsolation:
    async def test_per_host_failure_does_not_abort_others(self):
        def fake(host, port, password):
            if host == "bad":
                raise RuntimeError("auth failed")

        result = await rotate_circuits(
            ["good1", "bad", "good2"],
            port=9051,
            password=None,
            rotator=fake,
            settle_seconds=0,
        )
        assert result["good1"] == "ok"
        assert result["good2"] == "ok"
        assert result["bad"].startswith("error:")


class TestParallelism:
    async def test_runs_rotators_concurrently(self):
        """Each rotator takes ~50ms; three hosts should complete much faster
        than 3×50ms if they run in parallel."""

        def slow(host, port, password):
            time.sleep(0.05)

        started = asyncio.get_event_loop().time()
        await rotate_circuits(
            ["a", "b", "c"], port=9051, password=None, rotator=slow, settle_seconds=0
        )
        elapsed = asyncio.get_event_loop().time() - started
        # Sequential would be ~150ms; parallel should be ~50ms + scheduling.
        assert elapsed < 0.12, f"rotation should be parallel, took {elapsed:.3f}s"


class TestSettleDelay:
    async def test_settle_seconds_adds_sleep_after_broadcast(self):
        started = asyncio.get_event_loop().time()
        await rotate_circuits(
            ["a"], port=9051, password=None, rotator=lambda *a: None, settle_seconds=0.1
        )
        elapsed = asyncio.get_event_loop().time() - started
        assert elapsed >= 0.1
        assert elapsed < 0.3  # upper bound for CI jitter
