from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from typing import Optional, List
from shared.database import get_db
from shared.models import Identity, LeakHit
from shared.schemas import Identity as IdentitySchema, IdentityUpdate, IdentityInsights
from ..deps import get_current_user
from sqlalchemy.orm import selectinload
from shared.utils.audit import AuditLogger
from shared.domain.services.identity_merging import IdentityMergingService

router = APIRouter()

# ── BUG FIX: /graph MUST be declared before /{identity_id} routes ──
# FastAPI routes are matched in declaration order. A literal path like /graph
# would be captured by /{identity_id} pattern if declared after it.

@router.get("/graph")
async def get_identity_graph(db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Query Side (CQRS #5): Visualizzazione ultra-veloce del grafo potenziata (DD).
    """
    # 1. Recupera Nodi Identità
    if current_user.role == "admin":
        identities_query = text("SELECT id, identifier, risk_score, type, is_protected FROM identities")
        ident_result = await db.execute(identities_query)
        
        # 2. Recupera Archi (Connessioni)
        edges_query = text("SELECT identity_id as source, leak_id as target FROM identity_leaks")
        edge_result = await db.execute(edges_query)
    else:
        identities_query = text("""
            SELECT id, identifier, risk_score, type, is_protected 
            FROM identities 
            WHERE tenant_id = :tenant_id
        """)
        ident_result = await db.execute(identities_query, {"tenant_id": current_user.tenant_id})
        
        # 2. Recupera Archi (Connessioni)
        edges_query = text("""
            SELECT il.identity_id as source, il.leak_id as target
            FROM identity_leaks il
            JOIN identities i ON il.identity_id = i.id
            WHERE i.tenant_id = :tenant_id
        """)
        edge_result = await db.execute(edges_query, {"tenant_id": current_user.tenant_id})
        
    identities = ident_result.mappings().all()
    edges = edge_result.mappings().all()
    
    # 3. Recupera Metadata Leak per i nodi del grafo
    leak_ids = list(set([e["target"] for e in edges]))
    leaks = []
    if leak_ids:
        leak_query = select(LeakHit).where(LeakHit.id.in_(leak_ids))
        l_result = await db.execute(leak_query)
        leaks = l_result.scalars().all()

    nodes = [
        {
            "id": i["id"], 
            "label": i["identifier"], 
            "type": "identity", 
            "risk": i["risk_score"], 
            "subType": i["type"],
            "isProtected": i["is_protected"]
        } for i in identities
    ]
    
    for l in leaks:
        nodes.append({
            "id": l.id, 
            "label": l.source, 
            "type": "leak", 
            "risk": l.severity_score,
            "status": l.status
        })
        
    return {
        "nodes": nodes, 
        "links": [{"source": e["source"], "target": e["target"]} for e in edges]
    }

@router.get("/{identity_id}/insights", response_model=IdentityInsights)
async def get_identity_insights(
    identity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Identity Insights (Q): Recupera l'analisi dettagliata di un'identità.
    """
    result = await db.execute(
        select(Identity)
        .options(selectinload(Identity.leaks))
        .where(Identity.id == identity_id)
    )
    identity = result.scalar_one_or_none()
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
        
    if current_user.role != "admin" and identity.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    slave_result = await db.execute(
        select(Identity).where(Identity.master_identity_id == identity.id)
    )
    slaves = slave_result.scalars().all()
    
    await AuditLogger.log(
        db, 
        user_id=current_user.id, 
        tenant_id=current_user.tenant_id,
        action="VIEW_IDENTITY_INSIGHTS",
        resource_type="identity",
        resource_id=identity_id,
        details={"identifier": identity.identifier}
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
        "last_seen": leaks[0].discovered_at if leaks else None
    }

@router.patch("/{identity_id}/protect", response_model=IdentitySchema)
async def toggle_identity_protection(
    identity_id: str,
    update: IdentityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
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
async def trigger_auto_merge(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Identity Merging (V): Esegue l'algoritmo di unione automatica.
    """
    merged_count = await IdentityMergingService.auto_merge_identities(db, current_user.tenant_id)
    return {"status": "success", "merged_count": merged_count}

@router.get("/")
async def search_identities(
    identifier: Optional[str] = None,
    type: Optional[str] = None,
    min_risk: Optional[int] = None,
    max_risk: Optional[int] = None,
    only_masters: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
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
    identifier: str,
    type: str = "person",
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new monitored identity.
    """
    new_identity = Identity(
        identifier=identifier,
        type=type,
        tenant_id=current_user.tenant_id,
        risk_score=0,
        is_protected=False
    )
    db.add(new_identity)
    
    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="CREATE_IDENTITY",
        resource_type="identity",
        details={"identifier": identifier, "type": type}
    )
    
    await db.commit()
    await db.refresh(new_identity)
    return new_identity
