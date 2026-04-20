from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam as sa_bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import get_db
from shared.domain.services.identity_upsert import upsert_identity
from shared.domain.services.merge_proposer import propose_and_merge
from shared.domain.services.risk_scoring_v2 import mark_dirty
from shared.models import Identity, LeakHit
from shared.schemas import Identity as IdentitySchema
from shared.schemas import IdentityInsights, IdentityUpdate
from shared.utils.audit import AuditLogger

from ..deps import get_current_user

router = APIRouter()

# ── BUG FIX: /graph MUST be declared before /{identity_id} routes ──
# FastAPI routes are matched in declaration order. A literal path like /graph
# would be captured by /{identity_id} pattern if declared after it.


@router.get("/graph")
async def get_identity_graph(
    limit: int = 500,
    min_risk: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Paginated identity topology for the frontend force-graph.

    The legacy implementation pulled every identity + every link for the
    tenant, which collapses under real-tenant scale (10k identities, 100k
    links). We now cap the node set:

      * Select the top ``limit`` identities ordered by ``risk_score DESC``
        (hard bound, defaults to 500 — force-graph-2d performance cliff).
      * Optionally filter by ``min_risk`` to focus on the riskier slice.
      * Only fetch links whose endpoint identity is in the selected set,
        so the resulting subgraph is closed.
      * Fetch the leak nodes reached by those links, not the universe.

    Admins can still request a cross-tenant view; non-admins are pinned to
    their own tenant.
    """
    # Sanitize bounds. Server-side clamp guards against accidental DoS from
    # a UI that forgot to cap the param.
    limit = max(1, min(int(limit), 2000))
    min_risk = max(0, min(int(min_risk), 100))

    # 1. Top-N identities (paginated, risk-ordered).
    ident_stmt = select(
        Identity.id,
        Identity.identifier,
        Identity.risk_score,
        Identity.type,
        Identity.is_protected,
    ).where(Identity.risk_score >= min_risk)
    if current_user.role != "admin":
        ident_stmt = ident_stmt.where(Identity.tenant_id == current_user.tenant_id)
    ident_stmt = ident_stmt.order_by(Identity.risk_score.desc(), Identity.id).limit(limit)
    identities = (await db.execute(ident_stmt)).mappings().all()

    if not identities:
        return {"nodes": [], "links": [], "truncated": False}

    # 2. Links scoped to the selected identity set — using text SQL here
    # preserves the original query shape for parity with cached views.
    ident_ids = [i["id"] for i in identities]
    edges_stmt = text("""
        SELECT identity_id AS source, leak_id AS target
          FROM identity_leaks
         WHERE identity_id IN :ids
    """).bindparams(sa_bindparam("ids", expanding=True))
    edges = (
        await db.execute(edges_stmt, {"ids": ident_ids})
    ).mappings().all()

    # 3. Leak nodes reached by the filtered link set.
    leak_ids = list({e["target"] for e in edges})
    leaks = []
    if leak_ids:
        leaks = (
            await db.execute(select(LeakHit).where(LeakHit.id.in_(leak_ids)))
        ).scalars().all()

    nodes = [
        {
            "id": i["id"],
            "label": i["identifier"],
            "type": "identity",
            "risk": i["risk_score"],
            "subType": i["type"],
            "isProtected": i["is_protected"],
        }
        for i in identities
    ]
    for lk in leaks:
        nodes.append({
            "id": lk.id,
            "label": lk.source,
            "type": "leak",
            "risk": lk.severity_score,
            "status": lk.status,
        })

    return {
        "nodes": nodes,
        "links": [{"source": e["source"], "target": e["target"]} for e in edges],
        # Client-visible flag so the UI can show "showing top N of M" when
        # the cap is reached without an extra round trip to COUNT(*).
        "truncated": len(identities) == limit,
    }


@router.get("/{identity_id}/insights", response_model=IdentityInsights)
async def get_identity_insights(
    identity_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Identity Insights (Q): Recupera l'analisi dettagliata di un'identità.
    """
    result = await db.execute(select(Identity).options(selectinload(Identity.leaks)).where(Identity.id == identity_id))
    identity = result.scalar_one_or_none()

    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    if current_user.role != "admin" and identity.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    slave_result = await db.execute(select(Identity).where(Identity.master_identity_id == identity.id))
    slaves = slave_result.scalars().all()

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="VIEW_IDENTITY_INSIGHTS",
        resource_type="identity",
        resource_id=identity_id,
        details={"identifier": identity.identifier},
    )
    await db.commit()

    leaks = sorted(identity.leaks, key=lambda x: x.discovered_at, reverse=True)

    return {
        "identity": identity,
        "leaks": leaks,
        "merged_identities": slaves,
        "total_leaks": len(leaks),
        "highest_severity": max([l.severity_score for l in leaks]) if leaks else 0,
        "first_seen": leaks[-1].discovered_at if leaks else None,
        "last_seen": leaks[0].discovered_at if leaks else None,
    }


@router.patch("/{identity_id}/protect", response_model=IdentitySchema)
async def toggle_identity_protection(
    identity_id: str, update: IdentityUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Identity Protection (#11): Marca un'identità come protetta (VIP).
    """
    result = await db.execute(select(Identity).where(Identity.id == identity_id))
    identity = result.scalar_one_or_none()

    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    if current_user.role != "admin" and identity.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    identity.is_protected = update.is_protected
    await db.commit()
    await db.refresh(identity)
    return identity


@router.post("/merge")
async def trigger_auto_merge(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """Identity merging v2 — evidence-based.

    Scans the tenant for pairs of active master identities that share one or
    more ``LeakHit`` rows, builds an evidence set per pair, and runs each
    pair through :func:`merge_identities`. Pairs whose aggregate confidence
    falls below the configured threshold are skipped (reported in
    ``skipped_weak``); pairs blocked by the VIP invariant are reported in
    ``skipped_invariant``.

    Masters whose risk cluster changed are flipped to ``risk_score_dirty``
    by the merge engine; this handler also issues a single ``mark_dirty``
    sweep over every resulting master so the next ``recompute_dirty`` tick
    refreshes scores deterministically.
    """
    report = await propose_and_merge(
        db, current_user.tenant_id, performed_by=current_user.id
    )
    if report["merged_count"]:
        master_ids = [p["master_id"] for p in report["pairs"]]
        await mark_dirty(db, master_ids)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="RUN_AUTO_MERGE",
        resource_type="identity",
        details={
            "merged_count": report["merged_count"],
            "skipped_weak": report["skipped_weak"],
            "skipped_invariant": report["skipped_invariant"],
        },
    )
    await db.commit()

    return {"status": "success", **report}


@router.get("/")
async def search_identities(
    identifier: Optional[str] = None,
    type: Optional[str] = None,
    min_risk: Optional[int] = None,
    max_risk: Optional[int] = None,
    only_masters: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Search and Discovery (#3): Ricerca avanzata identità.
    """
    query = select(Identity)

    if current_user.role != "admin":
        query = query.where(Identity.tenant_id == current_user.tenant_id)

    if only_masters:
        query = query.where(Identity.master_identity_id.is_(None))

    if identifier:
        query = query.where(Identity.identifier.ilike(f"%{identifier}%"))
    if type:
        query = query.where(Identity.type == type)
    if min_risk is not None:
        query = query.where(Identity.risk_score >= min_risk)
    if max_risk is not None:
        query = query.where(Identity.risk_score <= max_risk)

    result = await db.execute(query.order_by(Identity.risk_score.desc()))
    return result.scalars().all()


@router.post("/")
async def create_identity(
    identifier: str, type: str = "person", db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    """Create — or re-observe — a monitored identity.

    Routed through :func:`upsert_identity` so the canonical form
    (normalized_identifier) is always populated, repeat creates by different
    analysts converge on the same row, and concurrent requests cannot race
    into duplicate rows (the UNIQUE constraint makes the INSERT ... ON
    CONFLICT DO NOTHING path deterministic).
    """
    try:
        identity = await upsert_identity(db, current_user.tenant_id, identifier, type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="CREATE_IDENTITY",
        resource_type="identity",
        resource_id=identity.id,
        details={"identifier": identifier, "type": type},
    )
    await db.commit()
    return identity
