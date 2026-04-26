from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import bindparam as sa_bindparam
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import get_db
from shared.domain.services.entity_resolution import (
    CrossTenantMerge,
    InsufficientEvidence,
    VipInvariantViolation,
    aggregate_confidence,
    merge_identities,
    reverse_merge,
)
from shared.domain.services.identity_upsert import upsert_identity
from shared.domain.services.merge_proposer import (
    SHARED_LEAK_STRENGTH,
    choose_master,
    gather_shared_leak_pairs,
    propose_and_merge,
)
from shared.domain.services.risk_scoring_v2 import mark_dirty
from shared.models import Identity, LeakHit, MergeEvent
from shared.schemas import Identity as IdentitySchema
from shared.schemas import IdentityInsights, IdentityUpdate
from shared.utils.audit import AuditLogger

from ..deps import get_current_user

router = APIRouter()


class ReverseMergeBody(BaseModel):
    reason: str


class PairSelection(BaseModel):
    master_id: str
    slave_id: str


class ExecuteMergesBody(BaseModel):
    pairs: list[PairSelection]


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
    edges = (await db.execute(edges_stmt, {"ids": ident_ids})).mappings().all()

    # 3. Leak nodes reached by the filtered link set.
    leak_ids = list({e["target"] for e in edges})
    leaks = []
    if leak_ids:
        leaks = (await db.execute(select(LeakHit).where(LeakHit.id.in_(leak_ids)))).scalars().all()

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
        nodes.append(
            {
                "id": lk.id,
                "label": lk.source,
                "type": "leak",
                "risk": lk.severity_score,
                "status": lk.status,
            }
        )

    return {
        "nodes": nodes,
        "links": [{"source": e["source"], "target": e["target"]} for e in edges],
        # Client-visible flag so the UI can show "showing top N of M" when
        # the cap is reached without an extra round trip to COUNT(*).
        "truncated": len(identities) == limit,
    }


@router.get("/merges")
async def list_recent_merges(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Most recent merge events for the operator's tenant.

    Analysts use this to answer "what auto-merged in the last hour?" or
    to spot an unexpected merge they want to reverse. Non-admins see only
    their own tenant; the cap is hard-bounded server-side.
    """
    limit = max(1, min(int(limit), 200))
    stmt = select(MergeEvent)
    if current_user.role != "admin":
        stmt = stmt.where(MergeEvent.tenant_id == current_user.tenant_id)
    stmt = stmt.order_by(MergeEvent.performed_at.desc()).limit(limit)
    events = (await db.execute(stmt)).scalars().all()

    # Fetch identifier strings for the master/slave pairs in one batch so
    # the UI can show "alice@example.com ← bob@example.com" without N+1.
    all_ids = {e.master_id for e in events} | {e.slave_id for e in events}
    if all_ids:
        rows = (await db.execute(select(Identity).where(Identity.id.in_(all_ids)))).scalars().all()
        ident_map = {i.id: i for i in rows}
    else:
        ident_map = {}

    def _brief(ident: Identity | None):
        if ident is None:
            return None
        return {
            "id": ident.id,
            "identifier": ident.identifier,
            "type": ident.type,
            "is_protected": ident.is_protected,
        }

    return [
        {
            "id": e.id,
            "master": _brief(ident_map.get(e.master_id)),
            "slave": _brief(ident_map.get(e.slave_id)),
            "confidence": round(e.confidence, 3),
            "performed_at": e.performed_at.isoformat() if e.performed_at else None,
            "reversed_at": e.reversed_at.isoformat() if e.reversed_at else None,
            "reverse_reason": e.reverse_reason,
            "evidence_count": len(e.evidence or []),
            "is_active": e.reversed_at is None,
        }
        for e in events
    ]


@router.post("/merge/execute")
async def execute_selected_merges(
    body: ExecuteMergesBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Merge a caller-selected subset of candidate pairs.

    Evidence is re-derived from the current shared-leak state at execution
    time rather than taken from the request body — a mid-session ingestion
    that added or removed a shared leak between two identities should
    affect the confidence we see when executing. If a pair has no shared
    leaks (the operator somehow selected something stale), it is reported
    in ``skipped_no_evidence``; we never fabricate a merge.

    Returns a per-pair outcome dict so the UI can render green/amber rows
    after execution.
    """
    if not body.pairs:
        return {"merged": [], "skipped_weak": [], "skipped_invariant": [], "skipped_no_evidence": []}

    # Fetch shared-leak pairs for the tenant once; we use this as the
    # authoritative evidence source.
    shared_pair_map = await gather_shared_leak_pairs(db, current_user.tenant_id)

    merged: list[dict] = []
    skipped_weak: list[dict] = []
    skipped_invariant: list[dict] = []
    skipped_no_evidence: list[dict] = []

    for pair in body.pairs:
        master = await db.get(Identity, pair.master_id)
        slave = await db.get(Identity, pair.slave_id)
        if master is None or slave is None:
            skipped_no_evidence.append(
                {"master_id": pair.master_id, "slave_id": pair.slave_id, "reason": "identity missing"}
            )
            continue
        if master.tenant_id != current_user.tenant_id and current_user.role != "admin":
            skipped_no_evidence.append(
                {"master_id": pair.master_id, "slave_id": pair.slave_id, "reason": "cross-tenant"}
            )
            continue

        # Canonical-pair lookup ignores order; try both directions.
        key_a = (pair.master_id, pair.slave_id)
        key_b = (pair.slave_id, pair.master_id)
        shared_leaks = (
            shared_pair_map.get(key_a) or shared_pair_map.get(key_b) or shared_pair_map.get(tuple(sorted(key_a)))
        )
        if not shared_leaks:
            skipped_no_evidence.append(
                {"master_id": pair.master_id, "slave_id": pair.slave_id, "reason": "no shared leaks"}
            )
            continue

        evidence = [{"type": "shared_leak", "leak_id": lid, "strength": SHARED_LEAK_STRENGTH} for lid in shared_leaks]
        try:
            event = await merge_identities(
                db, master=master, slave=slave, evidence=evidence, performed_by=current_user.id
            )
            merged.append(
                {
                    "event_id": event.id,
                    "master_id": master.id,
                    "slave_id": slave.id,
                    "confidence": event.confidence,
                    "shared_leak_count": len(shared_leaks),
                }
            )
        except InsufficientEvidence:
            skipped_weak.append({"master_id": master.id, "slave_id": slave.id})
        except VipInvariantViolation:
            skipped_invariant.append({"master_id": master.id, "slave_id": slave.id})
        except CrossTenantMerge:
            skipped_no_evidence.append({"master_id": master.id, "slave_id": slave.id, "reason": "cross-tenant"})

    if merged:
        await mark_dirty(db, [m["master_id"] for m in merged])

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="EXECUTE_MERGES",
        details={
            "merged_count": len(merged),
            "skipped_weak": len(skipped_weak),
            "skipped_invariant": len(skipped_invariant),
            "skipped_no_evidence": len(skipped_no_evidence),
        },
    )
    await db.commit()
    return {
        "merged": merged,
        "skipped_weak": skipped_weak,
        "skipped_invariant": skipped_invariant,
        "skipped_no_evidence": skipped_no_evidence,
    }


@router.get("/merge/preview")
async def preview_auto_merges(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dry-run the evidence-based auto-merger.

    Returns the same kind of pair report that ``POST /identities/merge``
    would produce, but **does not commit** any merge. Lets analysts review
    candidates and their confidence scores before triggering.
    """
    pairs = await gather_shared_leak_pairs(db, current_user.tenant_id)
    preview: list[dict] = []
    for (id_a, id_b), shared_leaks in list(pairs.items())[:50]:
        a = await db.get(Identity, id_a)
        b = await db.get(Identity, id_b)
        if a is None or b is None:
            continue
        if a.master_identity_id is not None or b.master_identity_id is not None:
            continue
        master, slave = choose_master(a, b)
        evidence = [{"type": "shared_leak", "leak_id": lid, "strength": SHARED_LEAK_STRENGTH} for lid in shared_leaks]
        conf = aggregate_confidence(evidence)
        preview.append(
            {
                "master": {
                    "id": master.id,
                    "identifier": master.identifier,
                    "risk_score": master.risk_score,
                    "is_protected": master.is_protected,
                },
                "slave": {
                    "id": slave.id,
                    "identifier": slave.identifier,
                    "risk_score": slave.risk_score,
                    "is_protected": slave.is_protected,
                },
                "confidence": round(conf, 3),
                "shared_leak_count": len(shared_leaks),
            }
        )
    preview.sort(key=lambda p: p["confidence"], reverse=True)
    return {"count": len(preview), "pairs": preview[:20]}


@router.post("/merges/{event_id}/reverse")
async def reverse_merge_event(
    event_id: str,
    body: ReverseMergeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Soft-reverse a merge event.

    Marks ``MergeEvent.reversed_at`` so the ledger stays append-only,
    restores the slave's independence (``master_identity_id = NULL``) and
    flips both master and slave to ``risk_score_dirty`` so the next
    recompute tick refreshes their scores.

    Fails with 403 cross-tenant, 404 if the event is not found, 409 if
    the event is already reversed (caller can re-check history).
    """
    event = (await db.execute(select(MergeEvent).where(MergeEvent.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Merge event not found")
    if current_user.role != "admin" and event.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if event.reversed_at is not None:
        raise HTTPException(status_code=409, detail="Merge event already reversed")

    await reverse_merge(db, event, reason=body.reason, reversed_by=current_user.id)

    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=event.tenant_id,
        action="REVERSE_MERGE",
        resource_type="merge_event",
        resource_id=event_id,
        details={
            "reason": body.reason,
            "master_id": event.master_id,
            "slave_id": event.slave_id,
        },
    )
    await db.commit()
    return {"status": "reversed", "event_id": event_id}


@router.get("/{identity_id}/merges")
async def identity_merge_history(
    identity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All merge events (active + reversed) involving a specific identity,
    either as master or slave. Used by the Identity Insights modal's
    'Merge history' tab.
    """
    # Tenant gate first — protect against existence-probing across tenants.
    ident = (await db.execute(select(Identity).where(Identity.id == identity_id))).scalar_one_or_none()
    if ident is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.role != "admin" and ident.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Identity not found")

    stmt = (
        select(MergeEvent)
        .where(
            MergeEvent.tenant_id == ident.tenant_id,
            (MergeEvent.master_id == identity_id) | (MergeEvent.slave_id == identity_id),
        )
        .order_by(MergeEvent.performed_at.desc())
        .limit(100)
    )
    events = (await db.execute(stmt)).scalars().all()

    counterpart_ids = {(e.slave_id if e.master_id == identity_id else e.master_id) for e in events}
    counterpart_rows = (
        (await db.execute(select(Identity).where(Identity.id.in_(counterpart_ids)))).scalars().all()
        if counterpart_ids
        else []
    )
    counter_map = {i.id: i for i in counterpart_rows}

    return [
        {
            "id": e.id,
            "role": "master" if e.master_id == identity_id else "slave",
            "counterpart": (
                {
                    "id": c.id,
                    "identifier": c.identifier,
                    "type": c.type,
                    "is_protected": c.is_protected,
                }
                if (c := counter_map.get(e.slave_id if e.master_id == identity_id else e.master_id))
                else None
            ),
            "confidence": round(e.confidence, 3),
            "performed_at": e.performed_at.isoformat() if e.performed_at else None,
            "reversed_at": e.reversed_at.isoformat() if e.reversed_at else None,
            "reverse_reason": e.reverse_reason,
            "evidence_count": len(e.evidence or []),
            "is_active": e.reversed_at is None,
        }
        for e in events
    ]


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
        "highest_severity": max(leak.severity_score for leak in leaks) if leaks else 0,
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
    report = await propose_and_merge(db, current_user.tenant_id, performed_by=current_user.id)
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
    identifier: str | None = None,
    type: str | None = None,
    min_risk: int | None = None,
    max_risk: int | None = None,
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
