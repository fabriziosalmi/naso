# AI Co-Analyst

The Co-Analyst is a tool-calling agent embedded in the NASO UI. You ask it a
question in natural language; it queries NASO's own data through a fixed set of
tools, and streams back its reasoning, the calls it made, and the results.

This page covers the in-application agent. To drive NASO from an external
assistant such as Claude Desktop instead, see
[MCP Integration](/guide/mcp-integration) — same data, different entry point.

## Bring your own model

NASO ships no model and calls no hosted API. It talks to any
OpenAI-compatible endpoint you point it at:

```bash
AI_ENDPOINT=http://localhost:1234/v1     # LM Studio, Ollama, vLLM, …
AI_MODEL=gemma-4-e2b-it
AI_ENABLE_THINKING=false
```

From inside Docker, `localhost` is the container. Use
`http://host.docker.internal:1234/v1` to reach a model server running on your
host — `docker-compose.yml` already adds the `host.docker.internal` host entry
for this.

This is a deliberate design choice, not an omission. The Co-Analyst reads
breach records and identity data; sending that to a third-party inference API
would export the exact material the operator is trying to contain. A local
model keeps it on your infrastructure.

Check what the API can see:

```bash
curl -s localhost:8000/ai/health | jq
```

## The agent loop

`POST /ai/chat` streams Server-Sent Events. Each event is one JSON object:

| `type` | Payload |
|---|---|
| `text` | An incremental chunk of the assistant's prose. |
| `tool_call` | `{id, name, args}` — the model is invoking a tool. |
| `tool_result` | `{id, name, data}` — what the tool returned. |
| `error` | `{message}` — the turn failed. |

The loop runs for at most **five** iterations (`DEFAULT_MAX_ITERATIONS` in
`shared/domain/services/ai_agent.py`) before it must answer. A small model that
gets stuck calling tools in a circle therefore stops rather than running away
with your context window and your GPU.

The frontend renders `tool_result` events into an evidence panel alongside the
prose, so every claim in the answer has the query that produced it sitting next
to it. That is the intended way to read the output: the tool results are the
finding, the prose is a summary of them.

## What the model is allowed to do

The toolkit is a fixed allow-list in
`shared/domain/services/ai_toolkit.py`. There is no general code execution and
no arbitrary SQL.

### Read

| Tool | Purpose |
|---|---|
| `search_identities` | Find monitored identities by identifier fragment, type or minimum risk score. |
| `get_identity_insights` | Full profile for one identity — breach history, risk timeline, aliases. |
| `get_leaks` | Breach records, filtered by source, severity or triage status. |
| `dark_web_probe` | Live Ahmia search over Tor, with provenance (`via_tor`, `fetched_at`, `page`). |
| `get_merge_cluster` | The identities currently merged into one cluster. |
| `find_near_duplicates` | Identity pairs that look like the same person. |
| `propose_merges_preview` | Merge candidates with their evidence — proposes, does not execute. |
| `get_merge_events_history` | The merge ledger, including reversals. |
| `verify_audit_chain` | Walk the hash-chained audit log and report the first break. |

### Write

| Tool | Effect |
|---|---|
| `create_task` | Add a task to the active investigation plan. |
| `flag_critical` | Change a leak's triage status (`new`, `reviewing`, `resolved`, `escalated`). |
| `toggle_identity_vip` | Set or clear VIP protection on an identity. |

Three write tools, all reversible, none destructive. The model can flag, tag
and propose; it cannot delete a record, execute a merge, or change a
permission. `propose_merges_preview` is the shape to notice — the agent surfaces
candidates and a human executes.

## Investigation plans

The Co-Analyst writes into a structured plan rather than only into chat:

| Method | Path |
|---|---|
| `GET` / `POST` | `/ai/plans` |
| `PATCH` / `DELETE` | `/ai/plans/{id}` |
| `POST` | `/ai/plans/{id}/tasks` |
| `PATCH` | `/ai/plans/{id}/tasks/{taskId}` |

Pass `investigation_id` in the chat request to bind a conversation to a plan;
`create_task` then files into it. This is what makes a session's output
survive the session — a chat transcript is not an investigation record.

## Security posture

Every tool call executes **with the calling operator's tenant and role**. An
agent working for an analyst cannot reach data that analyst could not reach by
hand; there is no service account with elevated rights behind it.

Every call is written to the audit log with its arguments, under its own action
type (`AI_CHAT`, `AI_DARK_WEB_PROBE`, `AI_FLAG_LEAK`, `AI_TOGGLE_VIP`). AI
activity is attributable and reviewable after the fact, not anonymous.

::: warning Prompt injection is a live risk
The Co-Analyst reads attacker-supplied text: leak contents, dark web page
bodies, Telegram messages. Any of it can contain instructions aimed at the
model.

The fixed toolkit, the absence of destructive tools, the tenant-scoped
execution and the audit trail bound the damage — an injection cannot reach data
the operator could not, cannot delete anything, and cannot act invisibly. None
of that stops a model from being *persuaded* to file a misleading task or flag
the wrong record.

Treat Co-Analyst output as a lead to verify, not a finding to act on. The
evidence panel exists so that verification is one glance rather than a
re-investigation.
:::

## When the answers are poor

Small local models are usually the constraint rather than the tooling.

- **It never calls a tool.** The model does not support function calling well,
  or at all. Try a larger instruct-tuned model — this is the most common cause.
- **It calls tools but loops.** It will stop at five iterations. Narrow the
  question; "which identities link to this domain" works far better than
  "investigate this domain".
- **`/ai/health` reports the engine unavailable.** `AI_ENDPOINT` is wrong, or
  points at `localhost` from inside a container. Use
  `host.docker.internal`.
- **Answers contradict the evidence panel.** Believe the panel. The tool
  results are data; the prose is the model's summary of it.
