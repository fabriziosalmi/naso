# Dark Web Reconnaissance

NASO performs OSINT collection across `.onion` services through a dedicated Tor cluster + a hardened Ahmia client. This page covers the runtime moving pieces and the knobs in [`shared/domain/services/dark_web/config.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/dark_web/config.py).

## Topology

```
Worker  ──SOCKS5h──→  HAProxy  ──tcp──→  tor-1, tor-2, …, tor-5
                                            │
                                            └─→ exit relays → Ahmia
```

- 5 Tor instances behind HAProxy. Distributing requests across multiple circuits keeps any single hostile remote from rate-limiting NASO based on a single exit IP.
- HAProxy health-checks each tor; a dead instance falls out of rotation automatically.
- The whole cluster sits on the internal Docker bridge — clearnet egress from the workers happens only through this proxy. There's no fall-through.

## Ahmia client

[`shared/domain/services/dark_web/ahmia_client.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/dark_web/ahmia_client.py). Pipeline per query:

```
sanitize_query → token bucket → circuit breaker → retry loop → parse → dedup
```

### Sanitization

`sanitize_query` does NFKC normalization, strips ASCII control chars (except tab/newline/CR which the whitespace pass folds), collapses whitespace, and enforces `[min_query_length, max_query_length]`. Empty / oversized queries fail fast with `InvalidQuery` — they never hit the wire. Test: `backend/tests/test_ahmia_client.py`.

### Token bucket

A shared `TokenBucket` (`tokens_per_second`, `burst`) throttles egress so NASO behaves as a polite citizen of the Ahmia community resource. The default config (`DEFAULT_CONFIG` in `dark_web/config.py`) tuned for "won't get IP-banned"; production deployments don't need to change it.

### Circuit breaker

Three-state machine:

- `closed`: requests flow normally, consecutive failures counted.
- `open`: short-circuits with `CircuitBreakerOpen` until `recovery_timeout` elapsed.
- `half_open`: one probe; on success → closed, on failure → open.

When the breaker is open, `search()` returns the partial report it had ([`AhmiaSearchReport(pages_fetched=N, …)`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/dark_web/ahmia_client.py)). Better than failing the whole investigation when only the last page errored.

### Retry loop

On `5xx` and `429` responses: full-jitter exponential backoff (`base * 2^attempt`, then `random(0, base)`, capped at `retry_max_delay`). `4xx` other than 429 propagate immediately — retrying a 404 is wasted budget.

### Pagination

Up to `max_pages` fetched serially. Stop early when:
- a page returns no new (non-duplicate) results;
- `stop_on_all_duplicates` is on and the page is 100% duplicates.

Per-result provenance is added at parse time: `fetched_at`, `page`, `source="ahmia"`, `via_tor` (set when the HTTP client routes through `TOR_PROXY`). The frontend renders these as chips on each card.

### Result cache

Optional in-memory TTL cache (`InMemoryTTLCache`, bounded `cache_max_size`, default `cache_ttl_seconds = 300`). A repeat query within the window returns the cached `AhmiaSearchReport` with `cached: true`; the per-result `fetched_at` still reflects the original fetch time, so the analyst sees "pulled 2 minutes ago from cache" in the UI.

Cache is opt-out: pass `cache=None` and set `cache_ttl_seconds=0` to disable entirely.

### NEWNYM rotation

When `rotate_circuit_per_query=True` and `tor_control_hosts` is non-empty, the client broadcasts NEWNYM to every Tor control port before the first page fetch. Useful when an upstream is rate-limiting the cluster's exit IPs — NEWNYM forces fresh circuits.

The broadcast result lands in `AhmiaSearchReport.rotation_report = {host: "ok" | "error: ..."}`. The frontend's Tor pill tooltip shows it.

The actual signal is sent via `stem` ([`shared/domain/services/dark_web/tor_control.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/dark_web/tor_control.py)). `stem` is imported lazily so a clearnet-only deployment without `NASO_DARKWEB_ROTATE_CIRCUIT=on` doesn't pay the import cost.

## Output shape

Every successful search returns an `AhmiaSearchReport`:

```json
{
  "query": "company-name leak 2026",
  "results": [
    {
      "title": "...",
      "url": "...onion",
      "description": "...",
      "fetched_at": "2026-04-26T13:20:00+00:00",
      "page": 1,
      "source": "ahmia",
      "via_tor": true
    }
  ],
  "pages_fetched": 3,
  "duplicates_dropped": 7,
  "elapsed_seconds": 4.231,
  "cached": false,
  "rotation": { "tor1": "ok", "tor2": "ok", ... }
}
```

## API surface

| Endpoint                            | Method | Notes                                                    |
|-------------------------------------|--------|----------------------------------------------------------|
| `/leaks/recon/darkweb?q=<query>`    | GET    | Authenticated. Audit-logged (`DARK_WEB_RECON`).          |
| `/leaks/recon/shodan?ip=<ip>`       | GET    | Validates IP format; requires `SHODAN_API_KEY`.          |
| `/leaks/recon/telegram?channel=...` | GET    | Requires Telethon credentials (`TELEGRAM_API_*`).        |

Errors:

- `InvalidQuery` → HTTP 400 `Dark Web search failed: <reason>` (sanitization failure).
- `AhmiaUnavailable` → HTTP 503 `Dark Web node unreachable: <reason>` (retries + breaker exhausted).

Both wrap the underlying exception with a generic message — the actual upstream error stays in the worker log.

## Failure modes

| Symptom                              | Where to look                                               |
|--------------------------------------|-------------------------------------------------------------|
| Every search 503s                    | Tor cluster. See [Runbook → Tor cluster down](runbook.md#tor-cluster-down). |
| Searches succeed but 0 results       | Sanitization stripped the query, or upstream is empty       |
| Many 429s in `naso-worker-pipeline`  | Rate limit too generous; lower `rate_tokens_per_second`     |
| Repeated NEWNYM `error: ...`         | `tor_control_hosts` / `tor_control_password` mis-set        |

Tests: full unit suite for the pipeline in `backend/tests/test_ahmia_client.py`, cache TTL in `test_ahmia_cache.py`, NEWNYM broadcast in `test_tor_control.py`.
