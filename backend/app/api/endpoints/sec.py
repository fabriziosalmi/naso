"""fabgpt-sec handoff API.

Two endpoints, both guarded by the existing JWT auth (same dep as the rest
of the backend). The MCP-stdio server in backend/mcp_server.py is untouched;
this module is the HTTP path fabgpt-sec consumes.

  GET  /api/v1/sec/findings   poll handler: returns naso findings since a
                              cursor in NasoFinding shape (redacted).
  POST /api/v1/sec/test-fire  dev/ops helper: builds the SOAR request for
                              one existing leak and POSTs it to the
                              configured FABGPTSEC_SOAR_URL. Returns the
                              request that was made + the response status.
                              Use this to wire up + sanity-check the
                              connection without waiting for a real high-
                              severity ingestion event.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from shared.database import get_db
from shared.models import LeakHit
from shared.utils.sec_handoff import build_soar_request, leak_to_naso_finding

from ..deps import get_current_user

router = APIRouter()

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@router.get("/findings")
async def list_findings(
    since: str | None = Query(None, description="opaque cursor; pass back next_cursor from prev call"),
    min_severity: int = Query(0, ge=0, le=100),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Naso findings since a cursor, NasoFinding-shape (PII-redacted).

    Cursor is the ISO timestamp of the last item returned. Strict ordering by
    discovered_at ascending, id tiebreaker. `next_cursor` is null when fewer
    than `limit` items came back.
    """
    stmt = (
        select(LeakHit)
        .options(joinedload(LeakHit.identities))
        .where(LeakHit.tenant_id == current_user.tenant_id)
        .where(LeakHit.severity_score >= min_severity)
    )
    if since:
        stmt = stmt.where(LeakHit.discovered_at > since)
    stmt = stmt.order_by(LeakHit.discovered_at.asc(), LeakHit.id.asc()).limit(limit)

    result = await db.execute(stmt)
    leaks = result.unique().scalars().all()

    items = [leak_to_naso_finding(leak, list(leak.identities)) for leak in leaks]
    next_cursor = items[-1]["observed_at"] if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/test-fire")
async def test_fire_soar(
    leak_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Build the SOAR request for one existing leak + POST it to
    FABGPTSEC_SOAR_URL. Returns what was sent + the response. For wiring +
    smoke-test only; the production path will fire on insert (TODO).

    Required env:
      FABGPTSEC_SOAR_URL   — full URL to sec's /api/soar/inbound
      NASO_SOAR_HMAC_SECRET — shared secret with sec
    """
    soar_url = os.environ.get("FABGPTSEC_SOAR_URL", "")
    secret = os.environ.get("NASO_SOAR_HMAC_SECRET", "")
    if not soar_url or not secret:
        raise HTTPException(
            status_code=503,
            detail="FABGPTSEC_SOAR_URL and NASO_SOAR_HMAC_SECRET must be set",
        )

    stmt = (
        select(LeakHit)
        .options(joinedload(LeakHit.identities))
        .where(LeakHit.tenant_id == current_user.tenant_id)
        .where(LeakHit.id == leak_id)
    )
    leak = (await db.execute(stmt)).unique().scalar_one_or_none()
    if leak is None:
        raise HTTPException(404, f"leak {leak_id} not found in this tenant")

    finding = leak_to_naso_finding(leak, list(leak.identities))
    headers, body = build_soar_request(finding, secret=secret)
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.post(soar_url, content=body, headers=headers)
            return {
                "url": soar_url,
                "request_headers": {k: v for k, v in headers.items() if k != "X-Naso-Signature"}
                | {"X-Naso-Signature": "sha256=<redacted>"},
                "request_body_size": len(body),
                "response_status": r.status_code,
                "response_text": r.text[:512],
            }
        except httpx.HTTPError as e:
            raise HTTPException(502, f"sec_unreachable:{type(e).__name__}")
