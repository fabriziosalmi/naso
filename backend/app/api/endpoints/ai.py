"""
NASO AI Co-Analyst Endpoint
────────────────────────────
Integrates with any OpenAI-compatible local LLM (LM Studio, Ollama, etc.)
via the AI_ENDPOINT setting. Supports:
  - SSE streaming chat with tool calling
  - Server-side tool dispatch (search_identities, get_leaks, dark_web_probe, etc.)
  - Investigation plan and task CRUD
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
import hashlib
import orjson
from shared.core.jwt_manager import jwt_blacklist

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.config import settings
from shared.database import get_db
from shared.domain.services.darkweb_search import DarkWebSearchService
from shared.models import Identity, InvestigationPlan, InvestigationTask, LeakHit
from shared.utils.audit import AuditLogger

from ..deps import get_current_user

logger = logging.getLogger("naso-ai")
router = APIRouter()

# ─────────────────────────── Pydantic schemas ───────────────────────────────


class ChatMessage(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    tool_calls: list | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    investigation_id: str | None = None


class PlanCreate(BaseModel):
    title: str
    description: str | None = None


class TaskCreate(BaseModel):
    content: str


class TaskUpdate(BaseModel):
    status: str | None = None
    content: str | None = None


class PlanUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


# ─────────────────────────── Tool definitions ───────────────────────────────

NASO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_identities",
            "description": "Search monitored identities in NASO by identifier string or risk level. Use this to find specific people or accounts under investigation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Email, username, or name fragment to search for"},
                    "min_risk": {"type": "integer", "description": "Minimum risk score (0-100) to filter by"},
                    "type": {"type": "string", "description": "Identity type: person, email, username, phone, domain"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leaks",
            "description": "Retrieve data breach records from NASO database. Filter by source platform, minimum severity, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source platform, e.g. 'github', 'telegram', 'darkweb'",
                    },
                    "min_severity": {"type": "integer", "description": "Minimum severity score (0-100)"},
                    "status": {"type": "string", "description": "Leak status: new, reviewing, resolved"},
                    "limit": {"type": "integer", "description": "Max results to return (default 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dark_web_probe",
            "description": "Execute a real-time Dark Web search via Ahmia onion search engine. Use for fresh intelligence gathering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query to probe the dark web for"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_identity_insights",
            "description": "Get detailed forensic analysis of a specific monitored identity by its ID. Returns full breach history, risk timeline, and merged aliases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identity_id": {"type": "string", "description": "The UUID of the identity to analyze"},
                },
                "required": ["identity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Add a structured investigation task to the current investigation plan. Use this to track findings and next steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Description of the task or finding"},
                    "plan_id": {"type": "string", "description": "ID of the investigation plan to add the task to"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_critical",
            "description": "Update the status of a specific data leak for triage. Use to mark findings as reviewing or resolved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "leak_id": {"type": "string", "description": "UUID of the leak to update"},
                    "status": {"type": "string", "description": "New status: reviewing, resolved, escalated"},
                },
                "required": ["leak_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_identity_vip",
            "description": "Protect an identity by marking it as VIP (is_protected = true/false). Use this when an analyst requests to protect an identity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identity_id": {"type": "string", "description": "UUID of the identity"},
                    "is_protected": {"type": "boolean", "description": "True to protect, False to unprotect"},
                },
                "required": ["identity_id", "is_protected"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are NASO Co-Analyst, an expert AI forensic intelligence analyst embedded in the NASO Forensic Engine — a professional threat intelligence and breach investigation platform.

## Your Mission
Assist security analysts investigate data breaches, correlate digital identities, interpret threat intelligence signals, and build structured investigation workflows.

## Available Tools
You can call the following tools to fetch real-time NASO data:
- search_identities — find monitored identities by name or risk level
- get_leaks — retrieve breach records filtered by source, severity, or status
- dark_web_probe — run a live Dark Web search via Ahmia
- get_identity_insights — deep analysis of a specific identity (breach history, aliases)
- create_task — add a task or finding to the active investigation plan
- flag_critical — triage / update status of a specific breach record
- toggle_identity_vip — directly set an identity as VIP Protected (is_protected) in the backend.

## Investigation Protocol
When starting an investigation:
1. Clarify the objective with the analyst
2. Create a structured plan — call create_task for each step
3. Execute evidence-gathering with search tools
4. Synthesize findings precisely
5. Recommend concrete next actions

## Communication Style
- Forensic, precise, and professional
- Use proper security terminology (TTP, IOC, PII, etc.)
- Always cite evidence by ID (leak IDs, identity IDs)
- Flag critical findings clearly: ⚠️ CRITICAL
- Structure responses with clear sections for readability
- Be concise — analysts need actionable insights, not walls of text"""


# ─────────────────────────── Tool executor ───────────────────────────────────


async def execute_tool(
    tool_name: str, tool_args: dict, db: AsyncSession, current_user, investigation_id: str | None
) -> dict[str, Any]:
    """Execute a tool call and return structured result."""
    try:
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
            result = await db.execute(q.order_by(Identity.risk_score.desc()).limit(15))
            identities = result.scalars().all()
            return {
                "tool": "search_identities",
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

        elif tool_name == "get_leaks":
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
            result = await db.execute(q.order_by(LeakHit.severity_score.desc()).limit(limit))
            leaks = result.scalars().all()
            return {
                "tool": "get_leaks",
                "count": len(leaks),
                "data": [
                    {
                        "id": l.id,
                        "source": l.source,
                        "severity": l.severity_score,
                        "status": l.status,
                        "discovered_at": l.discovered_at.isoformat(),
                        "snippet": (l.content_snippet or "")[:120],
                    }
                    for l in leaks
                ],
            }

        elif tool_name == "dark_web_probe":
            query = tool_args.get("query", "")
            if not query:
                return {"tool": "dark_web_probe", "error": "Query required"}
            results = await DarkWebSearchService.search_onion_links(query)
            await AuditLogger.log(
                db,
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                action="AI_DARK_WEB_PROBE",
                details={"query": query, "count": len(results)},
            )
            await db.commit()
            return {"tool": "dark_web_probe", "query": query, "count": len(results), "data": results[:10]}

        elif tool_name == "get_identity_insights":
            identity_id = tool_args.get("identity_id", "")
            result = await db.execute(
                select(Identity).options(selectinload(Identity.leaks)).where(Identity.id == identity_id)
            )
            identity = result.scalar_one_or_none()
            if not identity:
                return {"tool": "get_identity_insights", "error": f"Identity {identity_id} not found"}
            leaks = sorted(identity.leaks, key=lambda x: x.discovered_at, reverse=True)
            return {
                "tool": "get_identity_insights",
                "identity": {
                    "id": identity.id,
                    "identifier": identity.identifier,
                    "type": identity.type,
                    "risk_score": identity.risk_score,
                    "is_protected": identity.is_protected,
                },
                "total_leaks": len(leaks),
                "highest_severity": max([l.severity_score for l in leaks]) if leaks else 0,
                "recent_leaks": [
                    {
                        "id": l.id,
                        "source": l.source,
                        "severity": l.severity_score,
                        "discovered_at": l.discovered_at.isoformat(),
                    }
                    for l in leaks[:5]
                ],
            }

        elif tool_name == "create_task":
            plan_id = tool_args.get("plan_id") or investigation_id
            content = tool_args.get("content", "")
            if not content:
                return {"tool": "create_task", "error": "content required"}
            task = InvestigationTask(plan_id=plan_id, content=content, status="pending", created_by="ai")
            if plan_id:
                db.add(task)
                await db.commit()
                await db.refresh(task)
                return {"tool": "create_task", "task_id": task.id, "content": content, "status": "created"}
            return {"tool": "create_task", "content": content, "status": "no_plan_selected"}

        elif tool_name == "flag_critical":
            leak_id = tool_args.get("leak_id", "")
            new_status = tool_args.get("status", "reviewing")
            result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
            leak = result.scalar_one_or_none()
            if not leak:
                return {"tool": "flag_critical", "error": f"Leak {leak_id} not found"}
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
            return {"tool": "flag_critical", "leak_id": leak_id, "old_status": old_status, "new_status": new_status}

        elif tool_name == "toggle_identity_vip":
            identity_id = tool_args.get("identity_id", "")
            is_protected = tool_args.get("is_protected", True)
            result = await db.execute(select(Identity).where(Identity.id == identity_id))
            identity = result.scalar_one_or_none()
            if not identity:
                return {"tool": "toggle_identity_vip", "error": f"Identity {identity_id} not found"}

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
            return {
                "tool": "toggle_identity_vip",
                "identity_id": identity_id,
                "is_protected": is_protected,
                "status": "success",
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return {"tool": tool_name, "error": str(e)}


# ─────────────────────────── Chat endpoint ───────────────────────────────────


@router.post("/chat")
async def ai_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Streaming AI chat with tool calling.
    Returns text/event-stream with events:
      {"type": "text", "content": "..."}
      {"type": "tool_call", "id": "...", "name": "...", "args": {...}}
      {"type": "tool_result", "id": "...", "name": "...", "data": {...}}
      {"type": "error", "message": "..."}
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in body.messages:
        msg: dict = {"role": m.role, "content": m.content}
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        if m.name:
            msg["name"] = m.name
        messages.append(msg)

    async def generate() -> AsyncGenerator[str, None]:
        redis_client = await jwt_blacklist.get_client()
        # Semantic Caching ID (SHA-256)
        semantic_string = orjson.dumps([{"r": m["role"], "c": m["content"]} for m in messages[1:]] + [str(current_user.tenant_id)])
        cache_key = f"ai_cache:{hashlib.sha256(semantic_string).hexdigest()}"
        
        cached_response = await redis_client.get(cache_key)
        if cached_response:
            logger.info(f"⚡ [AI SEMANTIC CACHE HIT] Bypassing LM Studio for {cache_key}")
            yield f"data: {json.dumps({'type': 'text', 'content': cached_response})}\n\n"
            yield "data: [DONE]\n\n"
            return

        async with httpx.AsyncClient(timeout=120.0) as client:
            # ─── Phase 1: Non-streaming call to detect tool calls ───
            try:
                resp = await client.post(
                    f"{settings.AI_ENDPOINT}/chat/completions",
                    json={
                        "model": settings.AI_MODEL,
                        "messages": messages,
                        "tools": NASO_TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.3,
                        "stream": False,
                    },
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                completion = resp.json()
            except httpx.ConnectError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI engine offline — check LM Studio at ' + settings.AI_ENDPOINT})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
                return

            choice = completion["choices"][0]
            message = choice["message"]

            # ─── Tool calling phase ───
            if choice.get("finish_reason") == "tool_calls" or message.get("tool_calls"):
                tool_calls = message.get("tool_calls", [])
                messages.append(message)

                for tc in tool_calls:
                    tc_id = tc.get("id", f"call_{tc['function']['name']}")
                    tc_name = tc["function"]["name"]
                    try:
                        tc_args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tc_args = {}

                    # Emit tool_call event to frontend
                    yield f"data: {json.dumps({'type': 'tool_call', 'id': tc_id, 'name': tc_name, 'args': tc_args})}\n\n"

                    # Execute the tool
                    tool_result = await execute_tool(tc_name, tc_args, db, current_user, body.investigation_id)

                    # Emit tool_result event
                    yield f"data: {json.dumps({'type': 'tool_result', 'id': tc_id, 'name': tc_name, 'data': tool_result})}\n\n"

                    # Append to messages for second LLM call
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": tc_name,
                            "content": json.dumps(tool_result),
                        }
                    )

                # ─── Phase 2: Streaming call for final response ───
                try:
                    full_response = ""
                    async with client.stream(
                        "POST",
                        f"{settings.AI_ENDPOINT}/chat/completions",
                        json={
                            "model": settings.AI_MODEL,
                            "messages": messages,
                            "temperature": 0.3,
                            "stream": True,
                        },
                        headers={"Content-Type": "application/json"},
                    ) as stream_resp:
                        async for line in stream_resp.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        full_response += content
                                        yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    pass
                    
                    if full_response.strip() and not globals().get("redis_client"): # We defined redis_client in generate()
                        redis_client = await jwt_blacklist.get_client()
                        semantic_string = orjson.dumps([{"r": m["role"], "c": m["content"]} for m in messages[1:]] + [str(current_user.tenant_id)])
                        cache_key = f"ai_cache:{hashlib.sha256(semantic_string).hexdigest()}"
                        await redis_client.setex(cache_key, 7200, full_response)

                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Stream error: {e}'})}\n\n"

            else:
                # ─── No tool calls — stream the direct response ───
                content = message.get("content", "")
                if content:
                    # Simulate streaming by yielding in chunks
                    chunk_size = 4
                    words = content.split(" ")
                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i : i + chunk_size])
                        if i + chunk_size < len(words):
                            chunk += " "
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

        yield "data: [DONE]\n\n"

        await AuditLogger.log(
            db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            action="AI_CHAT",
            details={"investigation_id": body.investigation_id},
        )
        with contextlib.suppress(Exception):
            await db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────── Health check ────────────────────────────────────


@router.get("/health")
async def ai_health():
    """Check if the local AI endpoint is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.AI_ENDPOINT}/models")
            resp.raise_for_status()
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            return {
                "status": "online",
                "endpoint": settings.AI_ENDPOINT,
                "active_model": settings.AI_MODEL,
                "available_models": models,
            }
    except Exception as e:
        return {"status": "offline", "endpoint": settings.AI_ENDPOINT, "error": str(e)}


# ─────────────────────────── Investigation Plans CRUD ────────────────────────


@router.get("/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(InvestigationPlan)
        .options(selectinload(InvestigationPlan.tasks))
        .where(InvestigationPlan.tenant_id == current_user.tenant_id)
        .order_by(InvestigationPlan.created_at.desc())
    )
    plans = result.scalars().all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "task_count": len(p.tasks),
            "completed_tasks": sum(1 for t in p.tasks if t.status == "completed"),
            "tasks": [
                {
                    "id": t.id,
                    "content": t.content,
                    "status": t.status,
                    "tool_used": t.tool_used,
                    "created_by": t.created_by,
                    "created_at": t.created_at.isoformat(),
                }
                for t in p.tasks
            ],
        }
        for p in plans
    ]


@router.post("/plans")
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    plan = InvestigationPlan(
        title=body.title,
        description=body.description,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    db.add(plan)
    await AuditLogger.log(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="CREATE_INVESTIGATION",
        details={"title": body.title},
    )
    await db.commit()
    await db.refresh(plan)
    return {"id": plan.id, "title": plan.title, "status": plan.status, "tasks": []}


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(InvestigationPlan).where(
            InvestigationPlan.id == plan_id,
            InvestigationPlan.tenant_id == current_user.tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if body.title is not None:
        plan.title = body.title
    if body.description is not None:
        plan.description = body.description
    if body.status is not None:
        plan.status = body.status
    await db.commit()
    return {"id": plan.id, "status": plan.status}


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(InvestigationPlan).where(
            InvestigationPlan.id == plan_id,
            InvestigationPlan.tenant_id == current_user.tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.delete(plan)
    await db.commit()
    return {"status": "deleted"}


@router.post("/plans/{plan_id}/tasks")
async def add_task(
    plan_id: str,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    plan_check = await db.execute(
        select(InvestigationPlan).where(
            InvestigationPlan.id == plan_id, InvestigationPlan.tenant_id == current_user.tenant_id
        )
    )
    if not plan_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Plan not found")

    task = InvestigationTask(plan_id=plan_id, content=body.content, created_by="user")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "content": task.content, "status": task.status}


@router.patch("/plans/{plan_id}/tasks/{task_id}")
async def update_task(
    plan_id: str,
    task_id: str,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(InvestigationTask).where(
            InvestigationTask.id == task_id,
            InvestigationTask.plan_id == plan_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.status is not None:
        task.status = body.status
    if body.content is not None:
        task.content = body.content
    await db.commit()
    return {"id": task.id, "status": task.status}
