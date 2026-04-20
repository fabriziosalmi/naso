"""Live E2E against a real LM Studio / Ollama endpoint.

These tests drive the NASO agent loop against a genuine LLM and check
that a seeded investigation produces the **shape** of responses we
expect — not exact tool-call arguments (model-sensitive, brittle) but
the class of tools invoked and the loop's termination.

Gating
------
Set ``LM_STUDIO_URL`` to the LM Studio / Ollama base URL
(``http://localhost:1234/v1`` for LM Studio, ``http://localhost:11434/v1``
for Ollama). With the var absent, every test in this file is skipped —
CI stays green without a running LLM.

Optionally set ``LM_STUDIO_MODEL`` to pin the model id; otherwise the
first model reported by ``/v1/models`` is used. A 60-second per-test
timeout is budgeted; a quantised 8B model usually returns in 2–6s per
agent round.

Run
----
::

    LM_STUDIO_URL=http://localhost:1234/v1 \
    pytest -m live backend/tests/e2e/test_ai_live.py -v

Out of scope
------------
* Exact prompt/response content assertions (brittle across models).
* Token accounting (different models, different tokenisers).
* Streaming output mechanics (tested elsewhere against a mock).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio

from shared.domain.services.ai_agent import DEFAULT_MAX_ITERATIONS, run_agent_loop
from shared.domain.services.ai_toolkit import NASO_TOOLS
from shared.domain.services.entity_resolution import merge_identities
from shared.domain.services.identity_upsert import upsert_identity
from shared.domain.services.leak_ingest import ingest_leak
from shared.models import identity_leaks

# All tests in this module require a live LLM — gate with the env var.
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.live,
    pytest.mark.skipif(
        "LM_STUDIO_URL" not in os.environ,
        reason="LM_STUDIO_URL not set — skipping live LLM E2E",
    ),
]


# ─── LM Studio / Ollama client ─────────────────────────────────────────────

async def _pick_model(base_url: str) -> str:
    model = os.getenv("LM_STUDIO_MODEL")
    if model:
        return model
    # Pick the first available model — LM Studio exposes /v1/models with
    # an OpenAI-compatible payload; Ollama matches.
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{base_url}/models")
        resp.raise_for_status()
        data = resp.json().get("data") or []
        if not data:
            pytest.skip("LLM endpoint reported no available models")
        return data[0]["id"]


@pytest_asyncio.fixture
async def live_llm_call():
    """Build an ``llm_call`` coroutine bound to the live endpoint."""
    base_url = os.environ["LM_STUDIO_URL"].rstrip("/")
    model = await _pick_model(base_url)
    # A single httpx client reused across the agent loop's iterations.
    client = httpx.AsyncClient(timeout=60.0)
    try:
        async def call(messages: list[dict]) -> dict:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "tools": NASO_TOOLS,
                    "tool_choice": "auto",
                    # Low temp + tight max_tokens keep the loop fast and
                    # deterministic enough for shape assertions.
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()
        yield call
    finally:
        await client.aclose()


@dataclass
class FakeUser:
    id: str
    tenant_id: str
    role: str = "analyst"


async def _collect(agen):
    out = []
    async for ev in agen:
        out.append(ev)
    return out


# ─── Fixture helpers ────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are NASO Co-Analyst, an expert AI forensic intelligence analyst. "
    "Use the available tools to investigate. Call tools when appropriate; "
    "answer concisely once you have enough evidence."
)


async def _seed_dataset(db, tenant_id: str):
    """Deterministic fixture: two identities sharing a leak + a leak whose
    near-duplicate gets re-ingested later. Gives the LLM enough signal to
    drive each of the three scripted prompts.
    """
    alice = await upsert_identity(db, tenant_id, "alice@example.com", "email")
    bob = await upsert_identity(db, tenant_id, "bob@example.com", "email")
    alice.risk_score, bob.risk_score = 75, 20
    await db.commit()

    # Shared leak linking alice + bob.
    shared = await ingest_leak(
        db, tenant_id=tenant_id, source="github",
        content="credentials leaked for alice@example.com and bob@example.com in 2023 dump",
        severity_score=82,
    )
    await db.execute(identity_leaks.insert().values(identity_id=alice.id, leak_id=shared.id))
    await db.execute(identity_leaks.insert().values(identity_id=bob.id, leak_id=shared.id))

    # Pre-existing merge so the second prompt's provenance tool has data.
    await merge_identities(
        db, master=alice, slave=bob,
        evidence=[{"type": "shared_leak", "leak_id": shared.id, "strength": 0.9}],
    )

    await db.commit()
    return alice, bob, shared


# ─── Prompts exercised ──────────────────────────────────────────────────────

@pytest.mark.timeout(60)
async def test_investigation_triggers_identity_lookup(
    corr_db, tenant, user, live_llm_call
):
    """Prompt 1: 'find the riskiest identity and show its cluster'.

    Shape expectation: the loop emits at least one ``tool_call`` event
    whose name matches one of the discovery tools, terminates with a
    final ``text`` event, and stays inside the iteration cap.
    """
    await _seed_dataset(corr_db, tenant.id)
    fake = FakeUser(id=user.id, tenant_id=tenant.id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Find the highest-risk monitored identity and show me its merge cluster."},
    ]
    events = await _collect(
        run_agent_loop(
            messages, db=corr_db, current_user=fake, llm_call=live_llm_call,
            max_iterations=DEFAULT_MAX_ITERATIONS,
        )
    )

    tool_names = [e["name"] for e in events if e["type"] == "tool_call"]
    assert any(n in {"search_identities", "get_merge_cluster", "get_identity_insights"} for n in tool_names), (
        f"expected a discovery tool in {tool_names}"
    )
    texts = [e for e in events if e["type"] == "text"]
    assert texts, "loop must emit a final text event"
    assert events[-1]["type"] in {"text", "error"}


@pytest.mark.timeout(60)
async def test_audit_integrity_question_triggers_verify(
    corr_db, tenant, user, live_llm_call
):
    """Prompt 2: 'did anyone tamper with the audit log today?'.

    Shape expectation: verify_audit_chain is called. If the model also
    calls get_merge_events_history, that's fine (related provenance).
    """
    await _seed_dataset(corr_db, tenant.id)
    fake = FakeUser(id=user.id, tenant_id=tenant.id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Did anyone try to tamper with the audit log today? Verify the integrity of the ledger."},
    ]
    events = await _collect(
        run_agent_loop(
            messages, db=corr_db, current_user=fake, llm_call=live_llm_call,
            max_iterations=DEFAULT_MAX_ITERATIONS,
        )
    )

    tool_names = [e["name"] for e in events if e["type"] == "tool_call"]
    assert "verify_audit_chain" in tool_names, (
        f"expected verify_audit_chain in {tool_names}"
    )


@pytest.mark.timeout(60)
async def test_near_dup_paste_triggers_find_near_duplicates(
    corr_db, tenant, user, live_llm_call
):
    """Prompt 3: pastes a variant of an existing breach snippet and asks
    whether NASO has seen it before.

    Shape expectation: find_near_duplicates is called.
    """
    _, _, shared = await _seed_dataset(corr_db, tenant.id)
    fake = FakeUser(id=user.id, tenant_id=tenant.id)

    paste = (
        "Credentials LEAKED for alice@example.com AND bob@example.com in 2023 dump"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"I just received this breach snippet — do we already have it?\n\n{paste}"},
    ]
    events = await _collect(
        run_agent_loop(
            messages, db=corr_db, current_user=fake, llm_call=live_llm_call,
            max_iterations=DEFAULT_MAX_ITERATIONS,
        )
    )

    tool_names = [e["name"] for e in events if e["type"] == "tool_call"]
    assert "find_near_duplicates" in tool_names, (
        f"expected find_near_duplicates in {tool_names}"
    )
    # When the tool runs, it must have found the seeded leak at Hamming ≤ 5.
    tool_results = [e for e in events if e["type"] == "tool_result" and e["name"] == "find_near_duplicates"]
    if tool_results:
        data = tool_results[0]["data"]
        assert data.get("match_count", 0) >= 1, "expected to match the seeded shared leak"
