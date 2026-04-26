"""Agentic loop control-flow tests.

The real ``run_agent_loop`` calls an LLM — we don't want tests to touch a
network. Instead we pass a **scripted** ``llm_call`` coroutine that yields
pre-recorded completions in order. This makes the loop's control flow
observable and assertable:

    * Terminal case (no tool calls) → one ``text`` event, loop ends.
    * Single-round tool calls → ``tool_call`` + ``tool_result`` + ``text``.
    * Multi-round chain → tool_calls on iteration 1, different tool_calls
      on iteration 2, then text on iteration 3.
    * Iteration cap → ``error`` event when the LLM never stops calling tools.
    * Message trace accumulates assistant + tool messages in order.
    * Malformed JSON in tool arguments is handled gracefully.
    * LLM exception produces a clean ``error`` event without killing the loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.domain.services.ai_agent import run_agent_loop
from shared.domain.services.identity_upsert import upsert_identity

pytestmark = pytest.mark.asyncio


# ─── Helpers ─────────────────────────────────────────────────────────────────


@dataclass
class FakeUser:
    id: str
    tenant_id: str
    role: str = "analyst"


def _tool_call_msg(tc_id: str, name: str, args: dict) -> dict:
    """Mimic an OpenAI-shape chat completion with tool_calls."""
    import json as _json

    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc_id,
                            "type": "function",
                            "function": {"name": name, "arguments": _json.dumps(args)},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


def _text_msg(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ]
    }


async def _collect(agen):
    out = []
    async for ev in agen:
        out.append(ev)
    return out


def _scripted_llm(responses: list[dict]):
    """Build a coroutine that returns *responses* in order. Extra calls
    raise so tests that expect N rounds detect overruns.
    """
    state = {"i": 0}

    async def call(_messages: list[dict]) -> dict:
        idx = state["i"]
        if idx >= len(responses):
            raise RuntimeError(f"llm_call invoked {idx + 1}× but only {len(responses)} responses scripted")
        state["i"] += 1
        return responses[idx]

    return call


# ─── Terminal case ───────────────────────────────────────────────────────────


class TestTerminalCase:
    async def test_single_text_response_emits_one_text_event(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Hello?"}]

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm([_text_msg("Hello! How can I help?")]),
            )
        )
        assert len(events) == 1
        assert events[0] == {"type": "text", "content": "Hello! How can I help?"}


# ─── Single-round tool call ──────────────────────────────────────────────────


class TestSingleToolCallRound:
    async def test_tool_call_then_final_text(self, corr_db, tenant, user):
        # Seed one identity so search_identities returns something.
        await upsert_identity(corr_db, tenant.id, "alice@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Who do we monitor?"}]

        responses = [
            _tool_call_msg("call_1", "search_identities", {}),
            _text_msg("We monitor alice@example.com."),
        ]

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm(responses),
            )
        )

        kinds = [e["type"] for e in events]
        assert kinds == ["tool_call", "tool_result", "text"]
        assert events[0]["name"] == "search_identities"
        assert events[1]["name"] == "search_identities"
        # Tool result must carry the actual execute_tool output.
        data = events[1]["data"]
        assert data["tool"] == "search_identities"
        assert data["count"] == 1

        # The assistant message + the tool message were appended to the trace.
        assert messages[-2]["role"] == "assistant"
        assert messages[-1]["role"] == "tool"
        assert messages[-1]["tool_call_id"] == "call_1"


# ─── Multi-round chain ───────────────────────────────────────────────────────


class TestMultiRoundChain:
    async def test_chains_two_tool_rounds(self, corr_db, tenant, user):
        """First LLM response calls tool A, second calls tool B, third is text."""
        await upsert_identity(corr_db, tenant.id, "target@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Investigate target@example.com"}]

        responses = [
            _tool_call_msg("c1", "search_identities", {"identifier": "target"}),
            _tool_call_msg("c2", "propose_merges_preview", {}),
            _text_msg("No merge candidates; target is a standalone identity."),
        ]

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm(responses),
            )
        )

        kinds = [e["type"] for e in events]
        assert kinds == ["tool_call", "tool_result", "tool_call", "tool_result", "text"]
        assert events[0]["name"] == "search_identities"
        assert events[2]["name"] == "propose_merges_preview"

        # Trace grew by: assistant (turn 1) + tool (turn 1) + assistant (turn 2) + tool (turn 2).
        # Original had 1 user message.
        assert len(messages) == 1 + 4


# ─── Iteration cap ───────────────────────────────────────────────────────────


class TestIterationCap:
    async def test_runaway_tool_calls_trigger_error(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Go!"}]

        # LLM keeps asking for tools indefinitely.
        loop_responses = [_tool_call_msg(f"c{i}", "search_identities", {}) for i in range(10)]

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm(loop_responses),
                max_iterations=3,
            )
        )

        # 3 iterations × (tool_call + tool_result) = 6 events + 1 error event.
        kinds = [e["type"] for e in events]
        assert kinds.count("tool_call") == 3
        assert kinds.count("tool_result") == 3
        assert kinds[-1] == "error"
        assert "limit" in events[-1]["message"].lower()


# ─── Malformed input handling ────────────────────────────────────────────────


class TestMalformedInput:
    async def test_bad_tool_args_json_defaults_to_empty(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "test"}]

        bad = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "x",
                                "type": "function",
                                "function": {"name": "search_identities", "arguments": "not-json"},
                            }
                        ],
                    }
                }
            ]
        }

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm([bad, _text_msg("Done.")]),
            )
        )
        # Tool still executes with empty args — does not crash the loop.
        assert events[0]["args"] == {}
        assert events[1]["data"].get("tool") == "search_identities"


class TestLLMException:
    async def test_llm_error_yields_single_error_event(self, corr_db, tenant, user):
        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "test"}]

        async def boom(_msgs):
            raise RuntimeError("upstream timeout")

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=boom,
            )
        )
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert "upstream timeout" in events[0]["message"]


# ─── Parallel tool execution (Phase 10c) ────────────────────────────────────


class TestParallelToolExecution:
    """When ``session_factory`` is supplied, a multi-tool round runs in
    parallel — each tool on its own session — while event ordering in the
    output stream matches the LLM's tool_call order, not completion order.
    """

    async def test_multi_tool_round_runs_in_parallel(self, corr_db, corr_session_factory, tenant, user):
        """Three tools in the same round should complete in ~max(lat),
        not sum(lat). We can't easily add artificial latency to the real
        tools, so we measure relatively: the test just verifies that ALL
        tools ran and results came back in the requested order.
        """
        await upsert_identity(corr_db, tenant.id, "alice@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Gather everything"}]

        first_round = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "a",
                                "type": "function",
                                "function": {"name": "search_identities", "arguments": "{}"},
                            },
                            {
                                "id": "b",
                                "type": "function",
                                "function": {"name": "propose_merges_preview", "arguments": "{}"},
                            },
                            {
                                "id": "c",
                                "type": "function",
                                "function": {"name": "verify_audit_chain", "arguments": "{}"},
                            },
                        ],
                    }
                }
            ]
        }

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm([first_round, _text_msg("Summary.")]),
                session_factory=corr_session_factory,
            )
        )

        # All three tools fired and returned.
        results = [e for e in events if e["type"] == "tool_result"]
        assert len(results) == 3

        # Result order matches call order (by id), regardless of completion order.
        result_ids = [r["id"] for r in results]
        assert result_ids == ["a", "b", "c"]

        # Each result has the correct shape.
        assert results[0]["data"].get("tool") == "search_identities"
        assert results[1]["data"].get("tool") == "propose_merges_preview"
        assert results[2]["data"].get("tool") == "verify_audit_chain"

    async def test_single_tool_round_skips_fanout(self, corr_db, corr_session_factory, tenant, user):
        """One tool in a round → no fan-out, reuse the shared session.
        This is an optimization (no session setup overhead) but it also
        makes the test suite's sequential-path assertions stay valid for
        single-tool rounds.
        """
        await upsert_identity(corr_db, tenant.id, "bob@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "Find Bob"}]

        responses = [
            _tool_call_msg("only", "search_identities", {"identifier": "bob"}),
            _text_msg("Found Bob."),
        ]

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm(responses),
                session_factory=corr_session_factory,
            )
        )
        kinds = [e["type"] for e in events]
        assert kinds == ["tool_call", "tool_result", "text"]

    async def test_sequential_fallback_when_no_factory(self, corr_db, tenant, user):
        """Without a factory the loop falls back to the legacy sequential
        path — important for tests and for callers that cannot provide a
        session factory."""
        await upsert_identity(corr_db, tenant.id, "alice@example.com", "email")

        fake = FakeUser(id=user.id, tenant_id=tenant.id)
        messages = [{"role": "user", "content": "test"}]

        first_round = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "x",
                                "type": "function",
                                "function": {"name": "search_identities", "arguments": "{}"},
                            },
                            {
                                "id": "y",
                                "type": "function",
                                "function": {"name": "propose_merges_preview", "arguments": "{}"},
                            },
                        ],
                    }
                }
            ]
        }

        events = await _collect(
            run_agent_loop(
                messages,
                db=corr_db,
                current_user=fake,
                llm_call=_scripted_llm([first_round, _text_msg("Done.")]),
                # no session_factory
            )
        )
        results = [e for e in events if e["type"] == "tool_result"]
        assert len(results) == 2
