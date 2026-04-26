"""
NASO AI Co-Analyst Endpoint
────────────────────────────
Integrates with any OpenAI-compatible local LLM (LM Studio, Ollama, etc.)
via the AI_ENDPOINT setting. Supports:
  - SSE streaming chat with **agentic** tool calling (multi-round ReAct loop)
  - Server-side tool dispatch via ``shared.domain.services.ai_toolkit``
  - Investigation plan and task CRUD

The tool dispatcher and agent loop live in ``shared.domain.services`` so
they can be unit-tested directly against a real AsyncSession without
standing up FastAPI — see ``tests/test_ai_toolkit.py`` and
``tests/test_ai_agent_loop.py``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from collections.abc import AsyncGenerator

import httpx
import orjson
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.config import settings
from shared.core.jwt_manager import jwt_blacklist
from shared.database import AsyncSessionLocal, get_db
from shared.domain.services.ai_agent import DEFAULT_MAX_ITERATIONS, run_agent_loop
from shared.domain.services.ai_toolkit import NASO_TOOLS
from shared.models import InvestigationPlan, InvestigationTask
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


SYSTEM_PROMPT = """You are NASO Co-Analyst, an expert AI forensic intelligence analyst embedded in the NASO Forensic Engine — a professional threat intelligence and breach investigation platform.

## Your Mission
Assist security analysts investigate data breaches, correlate digital identities, interpret threat intelligence signals, and build structured investigation workflows.

## Available Tools

### Discovery & triage
- `search_identities` — find monitored identities by name or risk level
- `get_leaks` — retrieve breach records filtered by source, severity, status
- `get_identity_insights` — deep analysis of a specific identity (breach history, aliases)
- `dark_web_probe` — run a live Ahmia search over the Tor-backed dark-web pipeline

### Correlation engine (v2) — prefer these when investigating provenance
- `get_merge_cluster` — the full merge tree rooted at an identity (master + every transitively-merged slave + recent merge events)
- `propose_merges_preview` — DRY-RUN the evidence-based auto-merger; returns candidate pairs with confidence scores, NOTHING is merged
- `get_merge_events_history` — reverse-chronological merges involving an identity; reveals "how did X end up merged under Y?"
- `find_near_duplicates` — SimHash fingerprint a content blob and return existing leaks within Hamming distance 5

### Ledger integrity
- `verify_audit_chain` — walks the tenant's hash-chained audit log and reports if it verifies

### Mutations (use sparingly, always after discovery)
- `create_task` — add a task or finding to the active investigation plan
- `flag_critical` — update status of a specific breach record (reviewing / resolved / escalated)
- `toggle_identity_vip` — set an identity as VIP Protected

## Investigation Protocol
1. **Clarify** the objective with the analyst
2. **Plan** — call `create_task` for each step
3. **Gather evidence** with the discovery tools; chain calls freely — you can call more tools after seeing results (the loop will keep running until you stop requesting tools, up to a bounded number of iterations)
4. **Synthesize** findings precisely, citing every non-obvious claim by evidence ID
5. **Recommend** concrete next actions

## Communication Style
- Forensic, precise, and professional
- Use proper security terminology (TTP, IOC, PII, etc.)
- Always cite evidence by ID (leak IDs, identity IDs, merge event IDs)
- Flag critical findings clearly: ⚠️ CRITICAL
- Structure responses with clear sections for readability
- Be concise — analysts need actionable insights, not walls of text"""


# The tool dispatcher lives in shared.domain.services.ai_toolkit so it can
# be unit-tested against a real AsyncSession without FastAPI / httpx. The
# agentic ReAct loop is in shared.domain.services.ai_agent. This file now
# only wires HTTP → loop → SSE.


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
        # Semantic cache key — collapses identical question+history under
        # one LLM roundtrip. Bypasses both the LLM and the agent loop on
        # hits, so cached responses return in a single SSE chunk.
        semantic_string = orjson.dumps(
            [{"r": m["role"], "c": m["content"]} for m in messages[1:]] + [str(current_user.tenant_id)]
        )
        cache_key = f"ai_cache:{hashlib.sha256(semantic_string).hexdigest()}"

        cached_response = await redis_client.get(cache_key)
        if cached_response:
            logger.info("⚡ [AI SEMANTIC CACHE HIT] bypassing LLM for %s", cache_key)
            yield f"data: {json.dumps({'type': 'text', 'content': cached_response})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Build an httpx-backed llm_call that the agent loop can iterate
        # against. The agent loop is stateless w.r.t. HTTP — we give it the
        # call function and it drives the conversation.
        async with httpx.AsyncClient(timeout=120.0) as client:

            async def llm_call(msgs: list[dict]) -> dict:
                try:
                    resp = await client.post(
                        f"{settings.AI_ENDPOINT}/chat/completions",
                        json={
                            "model": settings.AI_MODEL,
                            "messages": msgs,
                            "tools": NASO_TOOLS,
                            "tool_choice": "auto",
                            "temperature": 0.3,
                            "stream": False,
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    return resp.json()
                except httpx.ConnectError as exc:
                    raise RuntimeError(f"AI engine offline — check LM Studio at {settings.AI_ENDPOINT}") from exc

            full_text = ""
            async for event in run_agent_loop(
                messages,
                db=db,
                current_user=current_user,
                investigation_id=body.investigation_id,
                llm_call=llm_call,
                max_iterations=DEFAULT_MAX_ITERATIONS,
                # Enable parallel tool execution: every tool in a multi-
                # tool round opens its own session via AsyncSessionLocal.
                # Audit-chain writes are serialized per-tenant inside
                # ``write_audit`` so the hash chain stays intact.
                session_factory=AsyncSessionLocal,
            ):
                if event["type"] == "text":
                    # Chunk the final text so the UI gets a streaming feel
                    # even though the LLM call itself was non-streaming.
                    content = event["content"]
                    full_text += content
                    words = content.split(" ")
                    chunk_size = 4
                    for i in range(0, len(words), chunk_size):
                        piece = " ".join(words[i : i + chunk_size])
                        if i + chunk_size < len(words):
                            piece += " "
                        yield f"data: {json.dumps({'type': 'text', 'content': piece})}\n\n"
                else:
                    # tool_call / tool_result / error pass through unchanged.
                    yield f"data: {json.dumps(event)}\n\n"

            if full_text.strip():
                await redis_client.setex(cache_key, 7200, full_text)

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
