# AI Co-Analyst

The Co-Analyst is a chat surface attached to the analyst dashboard. Under the hood it's a multi-round ReAct loop ([`shared/domain/services/ai_agent.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/ai_agent.py)) talking to whatever local OpenAI-compatible model you point `AI_ENDPOINT` at. Tools execute server-side against the same database the dashboard reads.

## Why ReAct, not one-shot

The first version was a one-shot "tool use" pipeline: call the LLM once, run whatever tools it asked for, call it a second time to turn results into prose. That works for "show me the top 10 leaks" but falls over on multi-step investigations:

> "Find the riskiest identity, then show me its merge cluster, then verify the audit log around the most recent merge event."

A one-shot model has to decide all three calls up front, before seeing any data. The current implementation runs a bounded loop — up to `DEFAULT_MAX_ITERATIONS` (5) rounds of `LLM → tool calls → tool results → LLM`. The model can see what its first probe returned and decide what to ask next. The loop terminates when the model stops requesting tools.

## Loop semantics

```
for iteration in range(max_iterations):
    completion = await llm_call(messages)
    if not completion.tool_calls:
        yield {"type": "text", "content": completion.content}
        return                                  # natural termination
    for tc in completion.tool_calls:
        yield {"type": "tool_call", ...}
    results = await execute(tc, ...)            # parallel if session_factory given
    for r in results:
        yield {"type": "tool_result", ...}
        messages.append({"role": "tool", "tool_call_id": ..., "content": json.dumps(r)})
yield {"type": "error", "message": "iteration cap"}     # hard cap
```

The cap exists so a runaway model can't burn unbounded tokens. 5 rounds is comfortably above any realistic investigation depth — most flows we see end at 2-3 rounds.

## Streaming

The endpoint (`POST /ai/chat`) returns SSE. Event types:

| `type`         | Payload                                                | Notes                                              |
|----------------|--------------------------------------------------------|----------------------------------------------------|
| `tool_call`    | `{id, name, args}`                                     | Emitted *before* the tool runs, in the LLM's order |
| `tool_result`  | `{id, name, data}`                                     | Emitted after the tool returns                      |
| `text`         | `{content}`                                            | Final assistant prose; stream ends after this       |
| `error`        | `{message}`                                            | LLM error or iteration cap; stream ends             |

The SPA store ([`frontend/src/store/useNasoStore.js`](https://github.com/fabriziosalmi/naso/blob/main/frontend/src/store/useNasoStore.js)) appends each event to the chat history and renders incrementally. The right-hand "evidence panel" is just the last 20 `tool_result` events with the full JSON payload.

The fetch path includes the CSRF header; SSE reconnect uses exponential backoff + jitter (5 retries cap).

## Parallel execution

When the model asks for multiple tools in one round, the loop fans them out via `asyncio.gather`, each running on a fresh `AsyncSession` from the supplied `session_factory`. Three reasons:

1. `AsyncSession` isn't safe for concurrent use — two `db.execute` calls on one session corrupt internal state.
2. Audit rows written by parallel tools need independent commits, so a failure in one doesn't roll back the others.
3. Write serialization for the audit chain happens at the chain layer (per-tenant `asyncio.Lock` + Postgres advisory lock), not here.

If `session_factory` is `None` (tests, legacy callers), the loop falls back to sequential execution on the shared `db` session.

## Tool catalog

Tools live in [`shared/domain/services/ai_toolkit.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/ai_toolkit.py). Each tool is a function with a JSON schema; the OpenAI-compatible LLM sees them via the `tools=` argument.

| Tool                          | Purpose                                                                         |
|-------------------------------|---------------------------------------------------------------------------------|
| `search_identities`           | Find monitored identities by name fragment or risk threshold                    |
| `get_identity_insights`       | Deep profile for one identity — breach history, aliases, risk timeline          |
| `get_leaks`                   | Filter the leak table by source / severity / status                             |
| `dark_web_probe`              | Live Ahmia search through the Tor cluster                                       |
| `get_merge_cluster`           | Full merge tree rooted at an identity (master + transitive slaves + events)     |
| `propose_merges_preview`      | Dry-run the evidence-based auto-merger; returns candidate pairs + confidence     |
| `get_merge_events_history`    | Reverse-chronological merges involving an identity                              |
| `find_near_duplicates`        | SimHash a content blob, return existing leaks within Hamming distance 5         |
| `verify_audit_chain`          | Walk the tenant's audit chain, report the first broken row if any               |
| `create_task`                 | Add a task to the active investigation plan                                     |
| `flag_critical`               | Update a leak's status (reviewing / resolved / escalated / false_positive)      |
| `toggle_identity_vip`         | Mark an identity as VIP-protected (or remove the flag)                          |

Mutating tools (`create_task`, `flag_critical`, `toggle_identity_vip`) write the same audit row a normal API call would, attributed to the chat session's user.

## System prompt

```
You are NASO Co-Analyst, an expert AI forensic intelligence analyst
embedded in the NASO Forensic Engine — a professional threat
intelligence and breach investigation platform.

## Your Mission
Assist security analysts investigate data breaches, correlate digital
identities, interpret threat intelligence signals, and build structured
investigation workflows.

[... full prompt in backend/app/api/endpoints/ai.py:SYSTEM_PROMPT ...]

## Investigation Protocol
1. Clarify the objective with the analyst
2. Plan — call create_task for each step
3. Gather evidence with the discovery tools; chain calls freely
4. Synthesize findings precisely, citing every non-obvious claim by evidence ID
5. Recommend concrete next actions

## Communication Style
- Forensic, precise, and professional
- Always cite evidence by ID (leak IDs, identity IDs, merge event IDs)
- Flag critical findings clearly: ⚠️ CRITICAL
```

The "cite evidence by ID" rule is what makes the output verifiable — every claim the model makes is traceable back to a row the analyst can independently look up.

## Testing without a real LLM

Most behavior tests use a scripted mock LLM that returns canned `completion` dicts in sequence — see `backend/tests/test_ai_agent_loop.py`. The fixture works against `AsyncSession` directly (no FastAPI), so tests run fast and deterministically.

A real-LLM E2E suite is gated behind `LM_STUDIO_URL`:

```bash
LM_STUDIO_URL=http://host.docker.internal:1234/v1 pytest -m live backend/tests/e2e/
```

Tests there are **shape** assertions ("a tool of this name got called", "the loop terminated within 5 iterations") rather than exact-string assertions on the model's response — model output drifts between releases.

## Failure modes

| Symptom                                       | Cause                                                                 | Fix                                                       |
|-----------------------------------------------|-----------------------------------------------------------------------|-----------------------------------------------------------|
| Chat shows `⚠️ LLM error: ...`                | Endpoint unreachable or returned non-200                              | `curl $AI_ENDPOINT/models`; restart LM Studio / Ollama   |
| Chat shows iteration-cap error                | Model stuck in a tool-call loop                                       | Reduce max_iterations or improve the system prompt        |
| `tool_result` is `{"error": "..."}`           | Tool itself failed (e.g. malformed args from the LLM)                 | Check `naso-ai` logs; the loop continues anyway          |
| AI co-analyst panel shows the offline pill    | `/ai/health` returned `{"status": "offline"}`                         | Same as the first row                                     |

See also the [Runbook](runbook.md#llm-offline) for how the rest of the pipeline degrades gracefully when the LLM is down.
