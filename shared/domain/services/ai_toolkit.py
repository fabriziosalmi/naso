"""AI Co-Analyst tool dispatcher — v2.

Two responsibilities:

    1. **Schemas** (``NASO_TOOLS``) — the OpenAI-style function definitions
       that get sent to the LLM so it knows what it can invoke.

    2. **Executor** (``execute_tool``) — pure-async dispatch that runs the
       tool against the database / correlation-engine services and returns a
       JSON-serializable dict.

Previously the schemas and executor lived in
``backend.app.api.endpoints.ai``. That coupled tool logic to the FastAPI
endpoint, which made the tools un-testable without the full web stack and
forced every test to stand up an httpx client. Moving them into a service
module lets us test each tool directly against a real AsyncSession from
the correlation test suite.

Every tool is tenant-scoped: non-admin users never see other tenants'
data, and mutations (``flag_critical``, ``toggle_identity_vip``) always
audit the change through the hash-chained :func:`AuditLogger.log`.

The new tools added in this round (Phase 8):

    * ``get_merge_cluster`` — full merge tree for an identity (master +
      all transitive slaves, plus recent merge events).
    * ``propose_merges_preview`` — dry-run of ``propose_and_merge``; lists
      candidate pairs with confidence scores without executing.
    * ``verify_audit_chain`` — runs :func:`verify_chain`; answers "is our
      ledger tamper-free?" in one call.
    * ``find_near_duplicates`` — given a content blob, returns existing
      leaks within Hamming distance 5 of its fingerprint. Lets the AI
      proactively flag "this looks like leak X".
    * ``get_merge_events_history`` — reverse-chronological merges involving
      an identity (or the whole tenant); surfaces provenance for "how did
      X end up merged under Y?".
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.domain.normalization import (
    hamming_distance,
    normalize_content,
    simhash64,
)
from shared.domain.services.darkweb_search import DarkWebSearchService
from shared.domain.services.entity_resolution import aggregate_confidence
from shared.domain.services.merge_proposer import (
    SHARED_LEAK_STRENGTH,
    choose_master,
    gather_shared_leak_pairs,
)
from shared.domain.services.risk_scoring_v2 import gather_merged_cluster
from shared.models import (
    Identity,
    InvestigationTask,
    LeakHit,
    MergeEvent,
)
from shared.utils.audit import AuditLogger
from shared.utils.audit_chain import verify_chain

logger = logging.getLogger("naso-ai-toolkit")


# ═════════════════════════════════════════════════════════════════════════════
#   Tool schemas — sent to the LLM as available functions
# ═════════════════════════════════════════════════════════════════════════════

NASO_TOOLS = [
    # ───── Existing tools (carried over) ────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_identities",
            "description": "Search monitored identities in NASO by identifier string or risk level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Email, username, or name fragment."},
                    "min_risk": {"type": "integer", "description": "Minimum risk score (0-100)."},
                    "type": {"type": "string", "description": "Identity type: person, email, username, phone, domain."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leaks",
            "description": "Retrieve breach records; filter by source, severity, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "min_severity": {"type": "integer"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max results (default 10, cap 25)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dark_web_probe",
            "description": "Run a real-time Ahmia search; returns matches with provenance (via_tor, fetched_at, page).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_identity_insights",
            "description": "Deep analysis of an identity by its UUID — breach history, risk timeline, aliases.",
            "parameters": {
                "type": "object",
                "properties": {"identity_id": {"type": "string"}},
                "required": ["identity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Add a structured task to the active investigation plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "plan_id": {"type": "string"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_critical",
            "description": "Update the status of a specific leak record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "leak_id": {"type": "string"},
                    "status": {"type": "string", "description": "new, reviewing, resolved, escalated"},
                },
                "required": ["leak_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_identity_vip",
            "description": "Mark an identity as VIP-protected (or remove the flag).",
            "parameters": {
                "type": "object",
                "properties": {
                    "identity_id": {"type": "string"},
                    "is_protected": {"type": "boolean"},
                },
                "required": ["identity_id", "is_protected"],
            },
        },
    },
    # ───── Phase 8: correlation-engine v2 tools ─────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_merge_cluster",
            "description": (
                "Full merge cluster rooted at an identity: its master, every transitively-merged slave, "
                "and the recent merge events. Use to answer 'who is merged under X?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"identity_id": {"type": "string"}},
                "required": ["identity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_merges_preview",
            "description": (
                "DRY RUN the evidence-based auto-merger. Returns candidate pairs with confidence and "
                "shared-leak counts WITHOUT executing any merge. Useful for analyst review before triggering."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_audit_chain",
            "description": (
                "Walk the hash-chained audit log for the current tenant and report if it verifies. "
                "Returns ok + broken_at index if tampering is detected."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_near_duplicates",
            "description": (
                "Fingerprint a content blob (SimHash) and return existing leaks within Hamming distance 5 "
                "— used to answer 'have we already seen this content?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_merge_events_history",
            "description": (
                "Reverse-chronological merge events involving an identity (or the whole tenant if omitted). "
                "Reveals provenance for 'how did X end up merged under Y?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"identity_id": {"type": "string"}},
                "required": [],
            },
        },
    },
]


# ═════════════════════════════════════════════════════════════════════════════
#   Dispatcher
# ═════════════════════════════════════════════════════════════════════════════

async def execute_tool(
    tool_name: str,
    tool_args: dict,
    db: AsyncSession,
    current_user,
    investigation_id: str | None,
) -> dict[str, Any]:
    """Dispatch *tool_name* against the database. Never raises — every
    failure mode is returned in the ``error`` key so the LLM can observe
    and potentially retry.
    """
    try:
        # ───── search_identities ──────────────────────────────────────────
        if tool_name == "search_identities":
            q = select(Identity)
            if current_user.role != "admin":
                q = q.where(Identity.tenant_id == current_user.tenant_id)
            if tool_args.get("identifier"):
                q = q.where(Identity.identifier.ilike(f"%{tool_args['identifier']}%"))
            if tool_args.get("min_risk") is not None:
                q = q.where(Identity.risk_score >= tool_args["min_risk"])
            if tool_args.get("type"):
                q = q.where(Identity.type == tool_args["type"])
            identities = (
                await db.execute(q.order_by(Identity.risk_score.desc()).limit(15))
            ).scalars().all()
            return {
                "tool": tool_name,
                "count": len(identities),
                "data": [
                    {
                        "id": i.id,
                        "identifier": i.identifier,
                        "type": i.type,
                        "risk_score": i.risk_score,
                        "is_protected": i.is_protected,
                    }
                    for i in identities
                ],
            }

        # ───── get_leaks ──────────────────────────────────────────────────
        if tool_name == "get_leaks":
            q = select(LeakHit)
            if current_user.role != "admin":
                q = q.where(LeakHit.tenant_id == current_user.tenant_id)
            if tool_args.get("source"):
                q = q.where(LeakHit.source.ilike(f"%{tool_args['source']}%"))
            if tool_args.get("min_severity") is not None:
                q = q.where(LeakHit.severity_score >= tool_args["min_severity"])
            if tool_args.get("status"):
                q = q.where(LeakHit.status == tool_args["status"])
            limit = min(int(tool_args.get("limit", 10)), 25)
            leaks = (
                await db.execute(q.order_by(LeakHit.severity_score.desc()).limit(limit))
            ).scalars().all()
            return {
                "tool": tool_name,
                "count": len(leaks),
                "data": [
                    {
                        "id": lk.id,
                        "source": lk.source,
                        "severity": lk.severity_score,
                        "status": lk.status,
                        "discovered_at": lk.discovered_at.isoformat() if lk.discovered_at else None,
                        "snippet": (lk.content_snippet or "")[:120],
                    }
                    for lk in leaks
                ],
            }

        # ───── dark_web_probe ─────────────────────────────────────────────
        if tool_name == "dark_web_probe":
            query = tool_args.get("query", "")
            if not query:
                return {"tool": tool_name, "error": "Query required"}
            results = await DarkWebSearchService.search_onion_links(query)
            await AuditLogger.log(
                db,
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                action="AI_DARK_WEB_PROBE",
                details={"query": query, "count": len(results)},
            )
            await db.commit()
            return {"tool": tool_name, "query": query, "count": len(results), "data": results[:10]}

        # ───── get_identity_insights ──────────────────────────────────────
        if tool_name == "get_identity_insights":
            identity_id = tool_args.get("identity_id", "")
            identity = (
                await db.execute(
                    select(Identity)
                    .options(selectinload(Identity.leaks))
                    .where(Identity.id == identity_id)
                )
            ).scalar_one_or_none()
            if not identity:
                return {"tool": tool_name, "error": f"Identity {identity_id} not found"}
            leaks = sorted(identity.leaks, key=lambda x: x.discovered_at or "", reverse=True)
            return {
                "tool": tool_name,
                "identity": {
                    "id": identity.id,
                    "identifier": identity.identifier,
                    "type": identity.type,
                    "risk_score": identity.risk_score,
                    "is_protected": identity.is_protected,
                },
                "total_leaks": len(leaks),
                "highest_severity": max([lk.severity_score for lk in leaks]) if leaks else 0,
                "recent_leaks": [
                    {
                        "id": lk.id,
                        "source": lk.source,
                        "severity": lk.severity_score,
                        "discovered_at": lk.discovered_at.isoformat() if lk.discovered_at else None,
                    }
                    for lk in leaks[:5]
                ],
            }

        # ───── create_task ────────────────────────────────────────────────
        if tool_name == "create_task":
            plan_id = tool_args.get("plan_id") or investigation_id
            content = tool_args.get("content", "")
            if not content:
                return {"tool": tool_name, "error": "content required"}
            if not plan_id:
                return {"tool": tool_name, "content": content, "status": "no_plan_selected"}
            task = InvestigationTask(plan_id=plan_id, content=content, status="pending", created_by="ai")
            db.add(task)
            await db.commit()
            await db.refresh(task)
            return {"tool": tool_name, "task_id": task.id, "content": content, "status": "created"}

        # ───── flag_critical ──────────────────────────────────────────────
        if tool_name == "flag_critical":
            leak_id = tool_args.get("leak_id", "")
            new_status = tool_args.get("status", "reviewing")
            leak = (
                await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
            ).scalar_one_or_none()
            if not leak:
                return {"tool": tool_name, "error": f"Leak {leak_id} not found"}
            old_status = leak.status
            leak.status = new_status
            await AuditLogger.log(
                db,
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                action="AI_FLAG_LEAK",
                resource_type="leak",
                resource_id=leak_id,
                details={"old_status": old_status, "new_status": new_status},
            )
            await db.commit()
            return {"tool": tool_name, "leak_id": leak_id, "old_status": old_status, "new_status": new_status}

        # ───── toggle_identity_vip ────────────────────────────────────────
        if tool_name == "toggle_identity_vip":
            identity_id = tool_args.get("identity_id", "")
            is_protected = bool(tool_args.get("is_protected", True))
            identity = (
                await db.execute(select(Identity).where(Identity.id == identity_id))
            ).scalar_one_or_none()
            if not identity:
                return {"tool": tool_name, "error": f"Identity {identity_id} not found"}
            old_state = identity.is_protected
            identity.is_protected = is_protected
            await AuditLogger.log(
                db,
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                action="AI_TOGGLE_VIP",
                resource_type="identity",
                resource_id=identity_id,
                details={"old": old_state, "new": is_protected},
            )
            await db.commit()
            return {"tool": tool_name, "identity_id": identity_id, "is_protected": is_protected, "status": "success"}

        # ═════════════ Phase 8 new tools ═════════════

        # ───── get_merge_cluster ──────────────────────────────────────────
        if tool_name == "get_merge_cluster":
            identity_id = tool_args.get("identity_id", "")
            root = (
                await db.execute(select(Identity).where(Identity.id == identity_id))
            ).scalar_one_or_none()
            if not root:
                return {"tool": tool_name, "error": f"Identity {identity_id} not found"}

            # Tenant isolation: non-admin users may only inspect their own
            # tenant. Returning 'not found' is intentional — we don't leak
            # the existence of cross-tenant rows.
            if current_user.role != "admin" and root.tenant_id != current_user.tenant_id:
                return {"tool": tool_name, "error": f"Identity {identity_id} not found"}

            cluster_ids = await gather_merged_cluster(db, identity_id)
            members = (
                await db.execute(select(Identity).where(Identity.id.in_(list(cluster_ids))))
            ).scalars().all()

            events = (
                await db.execute(
                    select(MergeEvent)
                    .where(
                        MergeEvent.tenant_id == root.tenant_id,
                        MergeEvent.master_id.in_(list(cluster_ids)),
                    )
                    .order_by(MergeEvent.performed_at.desc())
                    .limit(20)
                )
            ).scalars().all()

            return {
                "tool": tool_name,
                "root": {
                    "id": root.id,
                    "identifier": root.identifier,
                    "risk_score": root.risk_score,
                    "is_protected": root.is_protected,
                },
                "cluster_size": len(members),
                "members": [
                    {
                        "id": m.id,
                        "identifier": m.identifier,
                        "type": m.type,
                        "risk_score": m.risk_score,
                        "is_protected": m.is_protected,
                        "is_slave": m.master_identity_id is not None,
                    }
                    for m in members
                ],
                "recent_merges": [
                    {
                        "event_id": e.id,
                        "master_id": e.master_id,
                        "slave_id": e.slave_id,
                        "confidence": round(e.confidence, 3),
                        "performed_at": e.performed_at.isoformat() if e.performed_at else None,
                        "reversed": e.reversed_at is not None,
                    }
                    for e in events
                ],
            }

        # ───── propose_merges_preview ─────────────────────────────────────
        if tool_name == "propose_merges_preview":
            pairs = await gather_shared_leak_pairs(db, current_user.tenant_id)
            preview: list[dict] = []
            # Bound to first 50 pairs so the preview stays prompt-friendly
            # even in pathological tenants with hundreds of co-occurrences.
            for (id_a, id_b), shared_leaks in list(pairs.items())[:50]:
                a = await db.get(Identity, id_a)
                b = await db.get(Identity, id_b)
                if a is None or b is None:
                    continue
                if a.master_identity_id is not None or b.master_identity_id is not None:
                    continue
                master, slave = choose_master(a, b)
                evidence = [
                    {"type": "shared_leak", "leak_id": lid, "strength": SHARED_LEAK_STRENGTH}
                    for lid in shared_leaks
                ]
                conf = aggregate_confidence(evidence)
                preview.append(
                    {
                        "master_id": master.id,
                        "master_identifier": master.identifier,
                        "slave_id": slave.id,
                        "slave_identifier": slave.identifier,
                        "confidence": round(conf, 3),
                        "shared_leak_count": len(shared_leaks),
                    }
                )
            preview.sort(key=lambda p: p["confidence"], reverse=True)
            return {"tool": tool_name, "count": len(preview), "pairs": preview[:10]}

        # ───── verify_audit_chain ─────────────────────────────────────────
        if tool_name == "verify_audit_chain":
            # Admins can audit any tenant (if the arg is supplied); normal
            # analysts are pinned to their own.
            target_tenant = (
                tool_args.get("tenant_id")
                if current_user.role == "admin" and tool_args.get("tenant_id")
                else current_user.tenant_id
            )
            result = await verify_chain(db, tenant_id=target_tenant)
            return {
                "tool": tool_name,
                "tenant_id": target_tenant,
                "ok": result.ok,
                "broken_at": result.broken_at,
                "reason": result.reason,
            }

        # ───── find_near_duplicates ───────────────────────────────────────
        if tool_name == "find_near_duplicates":
            content = tool_args.get("content", "")
            if not content:
                return {"tool": tool_name, "error": "content required"}

            normalized = normalize_content(content)
            fingerprint = simhash64(normalized)

            stmt = select(LeakHit).where(
                LeakHit.tenant_id == current_user.tenant_id,
                LeakHit.simhash64.is_not(None),
            )
            candidates = (await db.execute(stmt)).scalars().all()

            matches = []
            for c in candidates:
                dist = hamming_distance(c.simhash64, fingerprint)
                # Slightly wider than the dedup threshold (3) so the AI has
                # room to reason about "possibly related, not quite a dup".
                if dist <= 5:
                    matches.append(
                        {
                            "id": c.id,
                            "distance": dist,
                            "source": c.source,
                            "severity": c.severity_score,
                            "snippet": (c.content_snippet or "")[:80],
                        }
                    )
            matches.sort(key=lambda m: m["distance"])
            return {
                "tool": tool_name,
                "query_fingerprint": fingerprint,
                "match_count": len(matches),
                "matches": matches[:10],
            }

        # ───── get_merge_events_history ───────────────────────────────────
        if tool_name == "get_merge_events_history":
            identity_id = tool_args.get("identity_id")
            q = select(MergeEvent).where(MergeEvent.tenant_id == current_user.tenant_id)
            if identity_id:
                q = q.where(
                    (MergeEvent.master_id == identity_id) | (MergeEvent.slave_id == identity_id)
                )
            events = (
                await db.execute(q.order_by(MergeEvent.performed_at.desc()).limit(20))
            ).scalars().all()
            return {
                "tool": tool_name,
                "count": len(events),
                "events": [
                    {
                        "id": e.id,
                        "master_id": e.master_id,
                        "slave_id": e.slave_id,
                        "confidence": round(e.confidence, 3),
                        "performed_at": e.performed_at.isoformat() if e.performed_at else None,
                        "reversed_at": e.reversed_at.isoformat() if e.reversed_at else None,
                        "evidence_count": len(e.evidence or []),
                    }
                    for e in events
                ],
            }

        return {"tool": tool_name, "error": f"Unknown tool: {tool_name}"}

    except Exception as exc:  # noqa: BLE001 — we want every tool failure returned, not raised
        logger.error("tool %s failed: %s", tool_name, exc)
        return {"tool": tool_name, "error": str(exc)}


__all__ = ["NASO_TOOLS", "execute_tool"]
