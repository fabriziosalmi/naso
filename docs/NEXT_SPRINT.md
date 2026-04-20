# Next sprint — optional hardening

Everything in the correlation / audit / Tor / AI macro-roadmap is shipped
and tested. The four items below are **deferrable polish**: none of them
are blocking production, but each meaningfully upgrades either operator
trust (observability, audit UI), rollout confidence (E2E), or operator
workflow (merge drawer). Pick one per mini-sprint or bundle them if time
allows.

---

## 1. Real-LLM E2E for the agent loop

### Why

The agent loop (`shared/domain/services/ai_agent.py`) has 9 unit tests
that exercise control flow against a **scripted mock** LLM. That covers
every code path but leaves one unvalidated surface: whether real
LM Studio / Ollama completions — with their model-specific quirks in
`tool_calls` shape, `finish_reason` edge cases, and JSON-parsing
variability — still drive the loop to terminate cleanly.

### Acceptance criteria

- [ ] A `tests/e2e/test_ai_live.py` suite gated behind `LM_STUDIO_URL` env
  var. Skipped when the var is absent so CI and offline dev stay green.
- [ ] Covers three scripted user prompts that should each trigger a
  different tool chain:
  1. "Find the riskiest identity and show its merge cluster." → expects
     `search_identities` then `get_merge_cluster`.
  2. "Did anyone try to tamper with the audit log today?" → expects
     `verify_audit_chain`, optionally followed by
     `get_merge_events_history` if broken.
  3. "Paste this breach dump — is it already in the database?" (with a
     real near-duplicate from the seed fixtures) → expects
     `find_near_duplicates` with a Hamming-distance match.
- [ ] Each test asserts: (a) the loop terminated within
  `DEFAULT_MAX_ITERATIONS`, (b) at least one `tool_call` event matches
  an expected tool name, (c) the final `text` event is non-empty, (d) a
  `RUN_AUTO_MERGE` or equivalent audit row was written when the flow
  mutated state.

### Implementation notes

- Use the existing `seed_demo_data.py` to prepare a deterministic
  database; the tests run against a temp SQLite, not Postgres.
- The LLM is prompt-sensitive, so test assertions should be **shape**
  assertions (a tool of this name got called, not the exact argument
  string). Models get updated; rigid assertions rot.
- Budget a 60s per-test timeout. LM Studio at `llama-3.1-8b-instruct`
  sized models typically returns in 2–6s per round; a 3-round agent is
  comfortably under the cap.
- Run with `pytest -m live tests/e2e/` so these can be excluded from
  normal `make test`.

### Risks

- Flakiness on model-response shape — acknowledged, mitigate by
  shape-only asserts.
- LM Studio not running → skip cleanly. Do NOT fail the suite.

### Effort

0.5 day — the hard part is the fixture data, not the test.

---

## 2. OpenTelemetry span per tool call

### Why

We ship tools individually to the AI loop but have no unified
observability over them. In production, an analyst sees "the AI is slow"
without being able to answer "slow because of `dark_web_probe` calling
Ahmia, or because of `find_near_duplicates` scanning a 50k-leak
table?". OTel spans close that gap with one line of instrumentation per
tool and make the Grafana dashboard ("p95 tool latency by name") a
one-query affair.

### Acceptance criteria

- [ ] Every call to `execute_tool` opens an OTel span named
  `naso.ai_tool.<tool_name>` (one per invocation, not per retry).
- [ ] Span attributes include:
  - `tool.name` — duplicates span name but queryable as an attribute
  - `naso.tenant_id` — tenant-scoped filtering
  - `naso.user_id` — who triggered it
  - `naso.investigation_id` — when present
  - `naso.parallel` — bool (true when running via `asyncio.gather`)
  - `naso.ai_iteration` — 1-indexed agent-loop iteration
  - `naso.result.error` — string, present only on tool-returned error
- [ ] The agent loop opens a parent span `naso.ai_agent.turn` that
  wraps every iteration; tool spans are children of it.
- [ ] Cache hits on `dark_web_probe` set `naso.cache.hit=true` on the
  tool span (the underlying `AhmiaClient` already knows, just need to
  propagate).
- [ ] A single env flag `NASO_OTEL_ENABLED` toggles everything; when
  false, span creation is a no-op (no-op tracer is free).

### Implementation notes

- `opentelemetry-api` is already a dep; the SDK is already wired in
  `backend/app/main.py` for the FastAPI middleware.
- Add a thin `@traced_tool` decorator in a new
  `shared/utils/tracing.py` that wraps `execute_tool` without changing
  its signature. The current tool dispatcher can wear this decorator
  verbatim.
- The iteration index is available inside `run_agent_loop`; add an
  `ai_iteration` kwarg to `execute_tool` (defaulted) so the span knows
  which round it came from.
- For the "parent span" pattern, use
  `tracer.start_as_current_span("naso.ai_agent.turn")` at the top of
  each loop iteration.

### Downstream wins (free once this lands)

- Grafana dashboard: stacked latency per tool over time.
- Alert: `avg(naso.ai_tool.dark_web_probe.duration) > 30s for 5m` —
  signals Tor cluster or Ahmia degradation before operators notice.
- Cost attribution per tenant: sum span durations grouped by
  `naso.tenant_id`.

### Risks

- Adding `tool.name` both as span name AND attribute looks redundant.
  It is — but span names are indexed differently from attributes in most
  backends. Keep both.
- Avoid putting tool *arguments* on spans. They may contain PII
  (identifiers, leak content). Only names, counts, and booleans.

### Effort

0.5 day.

---

## 3. Merge-preview drawer (UI)

### Why

Clicking **Preview auto-merge candidates** in Cmd+K today fires a toast
with the candidate count. That's enough to tell the operator "there are
3 pairs to review", but it doesn't let them actually review.

The backend already exposes `GET /identities/merge/preview` returning
every candidate pair with confidence, shared leak count, master
identifier, slave identifier. We need a side-drawer UI that renders
that list, with:

- Per-pair checkbox (default checked when confidence ≥ 0.75)
- "Merge N selected" button that loops through checked pairs and calls
  the real merge (not preview)
- Undo: any merge just performed gets a transient "Reverse within 30s"
  hint that uses the existing `reverseMerge` action

### Acceptance criteria

- [ ] Radix `<Sheet>`-style drawer on the right, wired to
  `fetchMergePreview()`.
- [ ] Each row shows: master identifier, arrow, slave identifier,
  confidence bar, shared-leak count, "trust/skip/force" radio.
- [ ] "Execute selected merges" button batches sequential
  `POST /identities/merge` calls and shows a progress toast per pair.
- [ ] After execution, the drawer refreshes the preview (most pairs
  should now be gone because one side became a slave).
- [ ] Accessibility: focus is trapped inside the drawer while open,
  `Esc` closes, all buttons have `aria-label`.

### Implementation notes

- Entry point: extend `CommandMenu.jsx` so the "Preview auto-merge
  candidates" item opens the drawer (not just fires a toast). Dispatch
  `window.dispatchEvent(new CustomEvent('naso:open-merge-preview'))`;
  `App.jsx` listens and mounts the drawer.
- Reuse the existing `<Sheet>` wrapper from `components/ui/sheet.jsx`.
- Store: add `mergePreviewDrawerOpen` state + `setMergePreviewOpen`
  action.
- No new endpoint needed — preview already returns everything we need.

### Risks

- If the LLM co-analyst calls `propose_merges_preview` and the operator
  concurrently opens the drawer, there's a mild race on what the preview
  shows. Acceptable — the drawer refetches on open.

### Effort

1 day (includes drawer, state wiring, accessibility pass).

---

## 4. Audit integrity banner

### Why

`verifyAuditChain()` today pops a toast when called explicitly. A
tampered chain is a *critical* state — an operator should not have to
hit Cmd+K to learn about it. A red persistent banner at the top of the
shell, visible on every page, is the correct UX for "something is very
wrong and requires your attention".

### Acceptance criteria

- [ ] On app boot (after login), the shell calls `verifyAuditChain()`
  once in the background.
- [ ] Result is cached in the store with a 5-minute TTL so every route
  transition doesn't re-verify.
- [ ] When `ok=false`, render a persistent banner above `<Header>`:
  - Red `#FF453A` background with 8% opacity
  - `ShieldAlert` icon + "Audit chain integrity broken at row N" copy
  - Two buttons: "View audit log" (navigates to `/audit`) and
    "Dismiss for this session" (sets a session flag to stop
    displaying; re-verify on next login)
- [ ] Re-verification on demand from the user menu ("Check audit
  integrity now").
- [ ] Banner also shown if `verifyAuditChain` throws (network error) —
  amber tone, "Integrity check failed to run" copy, slightly less loud.

### Implementation notes

- New component `components/layout/AuditIntegrityBanner.jsx`.
- Store: add `auditIntegrity: { ok, broken_at, reason, total, checkedAt }`
  field. Action `refreshAuditIntegrity({ force = false })` with TTL
  guard.
- Dismissal state in `sessionStorage` keyed by
  `naso.audit_dismissed_until_hash=<self_hash_of_broken_row>` so a new
  tamper after dismissal re-shows the banner.

### Risks

- False positive on first deploy against legacy audit rows (pre-chain)
  — they have `prev_hash=None` and `self_hash=None` for entries created
  before the migration. The `verify_chain` walk correctly ignores them
  only if they're at the start of the chain. Consider: filter out rows
  with `self_hash IS NULL` before verifying, OR backfill them with a
  maintenance task.

### Effort

0.5 day.

---

## Recommended sequencing

1. **OpenTelemetry (#2)** — zero user-visible risk, enables observability
   for everything else.
2. **Audit banner (#4)** — small UI, high trust payoff.
3. **Merge drawer (#3)** — bigger UI chunk, best done after #2 so we can
   measure tool latency of the underlying calls.
4. **E2E with LM Studio (#1)** — does not block anything but is the
   safety net we want before the next feature round.

Total: ~2.5 days for the full set.
