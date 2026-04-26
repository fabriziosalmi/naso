"""CSRF protection using the double-submit cookie pattern.

Why this exists
---------------
The auth cookie ``naso_access_token`` is httpOnly + SameSite=Lax. SameSite
blocks the most common drive-by attacks but does not cover every CSRF
vector — top-level POST forms cross-site, subdomain confusion, GET-as-
mutation if anything regresses, etc. Adding a synchronizer token makes
the protection independent of the SameSite cookie semantics.

Mechanism
---------
On login the server emits a second cookie, ``naso_csrf`` (same lifetime,
non-httpOnly so JS can read it). The SPA reads the cookie and echoes the
value into a request header (``X-Naso-CSRF``) on every state-changing
request. The middleware below compares cookie ↔ header and 403s on
mismatch.

An attacker site cannot read the cookie (Same-Origin Policy on response
bodies), so it cannot inject the matching header — even though the
browser will happily attach the auth cookie to a forged form POST.

Exemptions
----------
* Safe methods (GET, HEAD, OPTIONS) — never mutate state.
* ``/auth/login`` — there is no session to protect yet, and the login
  flow itself issues the CSRF cookie.
* Requests that do not carry the auth cookie at all — typical
  Bearer-token / server-to-server callers (the webhook ingest, MCP).
  An attacker page in a browser cannot forge an Authorization header
  cross-origin, so CSRF is not the right control there; auth is.

Token rotation
--------------
The cookie is regenerated on every login. We deliberately don't rotate
on every request: the SPA caches the value at boot via
``document.cookie``, and rotating per-request would force a re-read on
every call. A 60-minute access-token lifetime puts a natural ceiling on
the token's exposure.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

CSRF_COOKIE_NAME = "naso_csrf"
CSRF_HEADER_NAME = "X-Naso-CSRF"
AUTH_COOKIE_NAME = "naso_access_token"

# Methods that don't change server state per RFC 7231 §4.2.1.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Path prefixes that are explicitly out of scope for this middleware.
# Login is the bootstrap that mints the CSRF token in the first place;
# /api/docs etc. are GET-only Swagger surfaces, already handled by the
# safe-method check, but listed here for clarity if Swagger ever adds a
# POST surface.
_EXEMPT_PATHS = ("/auth/login",)


def issue_csrf_token() -> str:
    """Return a fresh URL-safe random token (~32 bytes of entropy)."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, max_age: int) -> None:
    """Attach the CSRF cookie to *response*. Non-httpOnly on purpose: the
    SPA reads the value via ``document.cookie`` and echoes it back in the
    ``X-Naso-CSRF`` header. ``Secure`` follows the same flag the auth
    cookie uses, controlled by the ``NASO_COOKIE_SECURE`` env var.
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="lax",
        secure=os.getenv("NASO_COOKIE_SECURE", "false").lower() == "true",
        max_age=max_age,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    """Drop the CSRF cookie. Pair with auth-cookie deletion at logout."""
    response.delete_cookie(key=CSRF_COOKIE_NAME, samesite="lax", path="/")


class CSRFMiddleware(BaseHTTPMiddleware):
    """Enforce double-submit cookie equality on cookie-authenticated mutations."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if self._should_skip(request):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        # Use a constant-time compare so a worst-case attacker cannot use
        # response timing to learn parts of the token. The check fails
        # closed: missing cookie *or* missing header → 403.
        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )

        return await call_next(request)

    @staticmethod
    def _should_skip(request: Request) -> bool:
        if request.method in _SAFE_METHODS:
            return True
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _EXEMPT_PATHS):
            return True
        # Bearer / server-to-server callers: no auth cookie means the
        # browser-CSRF threat model doesn't apply. Auth itself happens
        # via the Authorization header, which an attacker page can't
        # forge cross-origin.
        return AUTH_COOKIE_NAME not in request.cookies
