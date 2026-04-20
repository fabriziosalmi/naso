"""Send ``NEWNYM`` to the local Tor cluster to rotate exit circuits.

Rationale
---------
NASO's Tor cluster exposes SOCKS on ports balanced by HAProxy, so any given
Ahmia probe is served through one of N Tor instances selected round-robin.
Without circuit rotation the same exit node is reused for minutes at a
time, which makes NASO easy to fingerprint both by Ahmia and by any onion
service we later deep-scrape.

Sending ``SIGNAL NEWNYM`` to a Tor instance tells it to build a fresh set
of circuits — new exit, new middle, new guard rotation as scheduled. We
broadcast the signal to every Tor in the cluster because HAProxy can route
the next request to any of them, so rotating only one would be a no-op
whenever the round-robin lands on an un-rotated peer.

Design
------
* Authentication uses ``HashedControlPassword`` on the Tor side — cookie
  auth would require a shared Docker volume across containers, which
  complicates deployment. The password is plumbed through the config
  layer so it ships via env var, never hard-coded.
* The rotate function is async + injectable. Production passes
  :func:`_stem_rotate_sync` which opens a stem controller, authenticates,
  sends the signal, and closes. Tests pass a stub that records calls.
* Failures are logged but never propagated: a degraded NEWNYM broadcast
  must not abort a search. Worst case the search uses the current circuit,
  which is still correct — just less anonymous than ideal.
* A short post-rotation sleep lets Tor finish tearing down old circuits
  before the first request goes out on a fresh one.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Iterable

logger = logging.getLogger("naso-darkweb-torctl")

# Signature of the per-host rotation callable: (host, port, password) → None.
# Synchronous because stem is a blocking library; we wrap it in
# ``asyncio.to_thread`` at the call site.
HostRotator = Callable[[str, int, str | None], None]


# ─── Default (production) rotator using stem ────────────────────────────────

def _stem_rotate_sync(host: str, port: int, password: str | None) -> None:
    """Open a Tor controller, authenticate, send NEWNYM, close.

    Imported lazily so the ``stem`` dependency is only required at runtime
    when rotation is actually enabled — tests (and setups that route
    clearnet via the ``dark_web`` config) don't need it installed.
    """
    from stem import Signal  # type: ignore[import-untyped]
    from stem.control import Controller  # type: ignore[import-untyped]

    # Treat an empty string as "no auth". Production should always set a
    # password; the None path is here so dev setups with auth disabled
    # (CookieAuthentication=0 AND HashedControlPassword unset) still work.
    with Controller.from_port(address=host, port=port) as controller:
        if password:
            controller.authenticate(password=password)
        else:
            controller.authenticate()
        controller.signal(Signal.NEWNYM)


# ─── Public coroutine ────────────────────────────────────────────────────────

async def rotate_circuits(
    hosts: Iterable[str],
    *,
    port: int,
    password: str | None,
    rotator: HostRotator | None = None,
    settle_seconds: float = 0.5,
) -> dict[str, str]:
    """Broadcast ``NEWNYM`` to every *host* in parallel.

    Returns a ``{host: status}`` dict where status is ``"ok"`` or an error
    message; callers can log the result but should not treat a partial
    failure as fatal.

    :param settle_seconds: sleep after the broadcast so Tor's circuit
        builder has a moment to swap in fresh paths before the first
        request goes out. Defaults to 500ms — short enough to feel
        instant, long enough to matter in practice.
    """
    hosts = list(hosts)
    if not hosts:
        return {}

    rotator = rotator or _stem_rotate_sync

    async def _do_one(host: str) -> tuple[str, str]:
        try:
            await asyncio.to_thread(rotator, host, port, password)
            return host, "ok"
        except Exception as exc:  # noqa: BLE001 — status is what we promise, not exceptions
            logger.warning("NEWNYM failed for %s:%d — %s", host, port, exc)
            return host, f"error: {exc.__class__.__name__}"

    pairs = await asyncio.gather(*[_do_one(h) for h in hosts])
    if settle_seconds > 0:
        await asyncio.sleep(settle_seconds)
    return dict(pairs)


__all__ = ["rotate_circuits", "HostRotator"]
