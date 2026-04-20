"""Agentic ReAct loop for the NASO Co-Analyst.

The first NASO shipped with a **one-shot** tool pipeline: call the LLM
once, execute whatever tools it requested, call the LLM a second time to
turn tool results into prose, done. That model cannot chain reasoning —
if the first round of results reveals that a deeper query is needed
("cluster X has 12 slaves, let me inspect the most-recent merge event"),
the analyst has to kick off a new turn manually.

This module runs a proper agentic loop:

    for iteration in range(max_iterations):
        reply = await llm_call(messages)
        if reply.tool_calls:
            execute all tool calls (in parallel if session_factory given)
            append results to messages
            continue        # LLM sees results, may call more tools
        else:
            stream reply content to the client
            break

Loop termination:
    * Natural — the LLM stops requesting tools; we emit the final prose
      and finish.
    * Hard cap — after ``max_iterations`` iterations of tool calls the
      loop yields an ``error`` event with a polite message. Default cap
      is 5, which is more than enough for any realistic investigation
      but small enough to bound token cost on a runaway model.

Parallel execution
------------------
When the caller supplies ``session_factory``, a round that contains more
than one tool call is executed via ``asyncio.gather`` with **a fresh
session per tool**. Three reasons:

    1. ``AsyncSession`` is not safe for concurrent use — two ``db.execute``
       calls on one session corrupt its internal state.
    2. Audit rows written by parallel tools need independent commits, so
       a failure in one does not take down the others.
    3. Write serialization is handled at the ``audit_chain`` layer (per-
       tenant ``asyncio.Lock`` + Postgres advisory lock), not here.

When ``session_factory`` is ``None`` the loop falls back to sequential
execution on the shared ``db`` session — same behaviour as before.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.services.ai_toolkit import NASO_TOOLS, execute_tool

logger = logging.getLogger("naso-ai-agent")

# Hard ceiling on tool-call iterations. Each iteration = one LLM roundtrip
# + N tool executions. 5 is comfortably above any realistic investigation
# depth while keeping worst-case token cost bounded.
DEFAULT_MAX_ITERATIONS = 5


# Type of the caller-provided LLM entry point. Receives the full message
# list and returns the OpenAI-style completion dict. Kept abstract so the
# FastAPI endpoint passes an httpx-backed implementation and tests pass a
# scripted mock.
LLMCall = Callable[[list[dict]], Awaitable[dict]]


# Signature of the session factory. Returns an async context manager that
# yields an AsyncSession. Matches ``sqlalchemy.orm.sessionmaker`` when
# bound to an async engine and matches ``shared.database.AsyncSessionLocal``.
SessionFactory = Callable[[], "contextlib.AbstractAsyncContextManager[AsyncSession]"]


async def run_agent_loop(
    messages: list[dict],
    *,
    db: AsyncSession,
    current_user,
    investigation_id: str | None = None,
    llm_call: LLMCall,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    session_factory: SessionFactory | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the ReAct loop and yield event dicts.

    Event types:
        * ``{"type": "tool_call", "id": ..., "name": ..., "args": ...}``
        * ``{"type": "tool_result", "id": ..., "name": ..., "data": ...}``
        * ``{"type": "text", "content": ...}`` — final assistant response
        * ``{"type": "error", "message": ...}`` — LLM error or iteration cap

    The *messages* list is mutated in place with every assistant turn and
    every tool result, so the caller can inspect the full trace after the
    generator is exhausted.
    """
    for iteration in range(max_iterations):
        try:
            completion = await llm_call(messages)
        except Exception as exc:
            logger.error("LLM call failed at iteration %d: %s", iteration, exc)
            yield {"type": "error", "message": f"LLM error: {exc}"}
            return

        choice = completion.get("choices", [{}])[0]
        message = choice.get("message", {}) or {}
        tool_calls = message.get("tool_calls") or []

        # ───── Terminal case: no tool calls → emit final text ────────────
        if not tool_calls:
            content = message.get("content", "") or ""
            if content:
                yield {"type": "text", "content": content}
            return

        # ───── Tool-calling case ─────────────────────────────────────────
        # Add the assistant message (which contains the tool_calls payload)
        # to the trace before executing. The LLM protocol requires the
        # assistant message + its tool results to appear in order.
        messages.append(message)

        prepared: list[tuple[str, str, dict]] = []
        for tc in tool_calls:
            tc_id = tc.get("id", f"call_{tc.get('function', {}).get('name', 'unknown')}")
            tc_name = tc.get("function", {}).get("name", "")
            try:
                tc_args = json.loads(tc.get("function", {}).get("arguments", "{}") or "{}")
            except json.JSONDecodeError:
                tc_args = {}
            prepared.append((tc_id, tc_name, tc_args))
            yield {"type": "tool_call", "id": tc_id, "name": tc_name, "args": tc_args}

        # Execution strategy:
        #   * No ``session_factory`` supplied (tests, legacy callers) — run
        #     sequentially on the shared ``db`` session. Deterministic and
        #     safe but misses the latency win when the LLM asks for many
        #     tools at once.
        #   * ``session_factory`` supplied + ≥2 tools — run in parallel,
        #     each tool on its own session via ``asyncio.gather``. Audit
        #     writes are serialized per-tenant by the lock inside
        #     ``audit_chain.write_audit``; tool-level transactions are
        #     independent so a partial failure in one does not poison
        #     the others.
        #   * ``session_factory`` supplied + 1 tool — no reason to fan
        #     out for a single call; reuse the shared session.
        parallelize = session_factory is not None and len(prepared) > 1

        if parallelize:
            async def _run_one(tc_id: str, tc_name: str, tc_args: dict):
                async with session_factory() as fresh_db:
                    res = await execute_tool(
                        tc_name, tc_args, fresh_db, current_user, investigation_id
                    )
                return tc_id, tc_name, res

            results = await asyncio.gather(
                *[_run_one(i, n, a) for i, n, a in prepared]
            )
            # Emit in the original (prepared) order so the SSE stream and
            # the message-trace match the LLM's tool_call order — not the
            # (nondeterministic) completion order.
            by_id = {tc_id: (tc_name, result) for tc_id, tc_name, result in results}
            for tc_id, tc_name, _ in prepared:
                result = by_id[tc_id][1]
                yield {"type": "tool_result", "id": tc_id, "name": tc_name, "data": result}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": json.dumps(result),
                    }
                )
        else:
            for tc_id, tc_name, tc_args in prepared:
                result = await execute_tool(
                    tc_name, tc_args, db, current_user, investigation_id
                )
                yield {"type": "tool_result", "id": tc_id, "name": tc_name, "data": result}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": json.dumps(result),
                    }
                )

        # Loop continues — next iteration calls the LLM with the tool
        # results folded into the message trace.

    # Exited the for-else without hitting a terminal branch → iteration cap.
    yield {
        "type": "error",
        "message": f"Agent reached the {max_iterations}-iteration limit without producing a final answer.",
    }


__all__ = ["run_agent_loop", "LLMCall", "DEFAULT_MAX_ITERATIONS", "NASO_TOOLS"]
