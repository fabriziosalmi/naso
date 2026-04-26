# Runbook

Operational playbooks. Keep this short and action-oriented — every entry should let on-call execute in under a minute.

## Triage map

```
The user-facing thing       │ First place to look
────────────────────────────┼──────────────────────────────────
Login fails for everyone    │ Redis (JWT blacklist)
Login fails for one user    │ Postgres + their hashed_password row
Audit banner is red         │ /system/audit/verify, then this page
Dark-web search 503s        │ Tor cluster + Ahmia upstream
AI co-analyst hangs         │ Local LLM endpoint reachability
Critical alerts not firing  │ SOAR webhook URL + signing secret
Backend 5xx                 │ /system/health composite probe
```

## /system/health composite probe

Always start here.

```bash
curl -fsS https://api.naso.example.com/system/health | jq .
```

Response shape:

```json
{
  "status": "ok | degraded | down",
  "services": {
    "postgres":      { "ok": true, "latency_ms": 8.2 },
    "redis":         { "ok": true, "latency_ms": 1.3 },
    "rabbitmq":      { "ok": true, "latency_ms": 4.7 },
    "minio":         { "ok": false, "latency_ms": 1000, "error": "timeout" },
    "elasticsearch": { "ok": true, "latency_ms": 22.0 }
  }
}
```

`down` = Postgres or Redis is gone (auth doesn't work). `degraded` = the other three: ingestion may be wedged but the dashboard still loads cached data. The endpoint is auth-free on purpose.

## Audit chain broken

Verify endpoint says `ok: false`.

```bash
curl -fsS https://api.naso.example.com/system/audit/verify | jq .
# {"ok": false, "broken_at": 4123, "reason": "self_hash mismatch (row content tampered)", ...}
```

This is **always evidence of tampering**. Treat as a security incident:

1. **Snapshot Postgres immediately** before someone closes the window. `pg_dump` to off-host storage.
2. Identify the broken row(s): the `broken_at` index is the first failing row in `timestamp ASC, id ASC` order.
3. Compare against the most recent backup that *did* verify. The diff is what the attacker touched.
4. Restore from the verified backup. Do not "fix forward" — the chain is the source of truth, you cannot rewrite history without leaving more evidence.
5. Rotate the JWT keypair (assume operator session compromise) — see "JWT key rotation" below.

For routine ops monitoring, `/system/audit/verify` should be polled every 5 minutes. The SPA's `AuditIntegrityBanner` does this automatically when an analyst is logged in.

## Tor cluster down

Symptom: dark-web searches return 503 or `Dark Web node unreachable`.

```bash
docker compose ps | grep naso-tor
# Expect: 5 instances + naso-tor-cluster (HAProxy) all "Up"
```

If only one tor is down, HAProxy will route around it; the cluster keeps serving. If all five are down or HAProxy itself is dead:

```bash
docker compose restart naso-tor-1 naso-tor-2 naso-tor-3 naso-tor-4 naso-tor-5 naso-tor-lb
```

Tor occasionally needs ~60 seconds after restart to reach 100% bootstrap. The Ahmia client's circuit breaker will open when failures stack up; check it via the breaker state log line in `naso-worker-pipeline`. The `rotate_circuit_per_query` config (see [dark-recon.md](dark-recon.md)) issues a NEWNYM signal per query — if the upstream is rate-limiting the cluster's exit IPs, this is what flips them.

If the issue persists, suspect Ahmia upstream. There's no mitigation; failover should be a second search backend (not currently implemented).

## LLM offline

Symptom: `/ai/health` returns `offline`, the AI co-analyst panel shows the offline pill.

```bash
curl -fsS http://host.docker.internal:1234/v1/models    # or wherever AI_ENDPOINT points
```

If the local LLM is down, the rest of NASO keeps working — the agent loop yields a graceful `error` event ([`shared/domain/services/ai_agent.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/ai_agent.py)) and the analyst falls back to manual investigation. Restart LM Studio / Ollama; check `AI_ENDPOINT` matches its bind address.

The pipeline's per-leak AI scoring also degrades gracefully: when `analyze_leak_with_gemma_thinking` raises `AIServiceError`, the pipeline downgrades severity to the YARA-only score and logs `event=ai_degraded`. Check `naso-worker-pipeline` logs for the count.

## Redis disconnected

Auth path requires Redis (JTI blacklist lookup). When Redis is gone:

- `is_blacklisted(jti)` raises → 401 for every authenticated request.
- Login itself still works (the JWT is minted), but the very next call lands on the blacklist check and 401s.

**Don't** patch around this by skipping the blacklist — it's how revocation works. Bring Redis back, or fail the request:

```bash
docker compose ps naso-cache
docker compose logs --tail=200 naso-cache
docker compose restart naso-cache
```

If Redis has lost its dataset (no AOF / RDB), all blacklisted tokens become valid again. Mitigation: if you suspect a stolen token, rotate the JWT keypair so every token (revoked or not) becomes invalid.

## RabbitMQ disconnected

Symptom: `/leaks/ingest/webhook` 5xx; the `/system/health` rabbitmq probe is red. The synchronous webhook path can't enqueue.

```bash
docker compose logs --tail=200 naso-broker
docker compose restart naso-broker
```

The Celery workers will reconnect automatically (aio_pika has built-in retry). The webhook caller, however, will see the failure during the outage window — there's no synchronous fallback queue, by design.

## SOAR webhook receiver not getting alerts

1. Check `SOAR_WEBHOOK_URL` is set (`docker exec naso-worker-pipeline env | grep SOAR`).
2. Check the receiver hasn't IP-blocked the egress.
3. Check the HMAC: receivers should:
   - reject when `|now - X-Naso-Timestamp|` > 5 min
   - recompute MAC over `<ts>.<body>` with their copy of the secret
   - `compare_digest` with the value in `X-Naso-Signature-256`
   The signing secret is `NASO_WEBHOOK_SIGNING_SECRET`. Both sides must hold it.
4. The pipeline only fires for `severity_score ≥ 90`. If you want to test, manually drop a high-severity row and tail `naso-worker-pipeline` logs for `[SOAR] Fired webhook to SIEM at ...`.

## JWT key rotation

The keypair is in `/run/secrets/JWT_PRIVATE_KEY` (and `/run/secrets/JWT_PUBLIC_KEY`). Rotation is not zero-downtime today — every existing session is invalidated.

```bash
# 1. Generate a new keypair offline (or via the project script).
python cli/generate_secrets.py --force      # writes new .secrets-mock/JWT_*; in prod do this via your secret manager

# 2. Roll the secret in your secret manager.
# 3. Restart the API and workers so they pick up the new key.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps backend worker-pipeline worker-massive

# 4. Force-logout all users by purging the blacklist (optional — every
#    old token is unverifiable already, but this clears the keys):
docker compose exec naso-cache redis-cli --scan --pattern 'blacklist:*' | xargs -r docker compose exec -T naso-cache redis-cli DEL
```

## Forensic signing key compromise

If `NASO_PRIVATE_KEY_PATH` (the dossier signing key) is suspected leaked: every dossier signed with it loses its forensic value. Rotate the key, generate a new public-key fingerprint, and publish a notice naming the cutoff timestamp. Older dossiers can still be verified against the old public key — they just shouldn't be trusted in court.

## Container won't start

Most "container exits immediately" reports are config issues. Standard diagnosis:

```bash
docker compose ps
docker compose logs --tail=200 <service>
docker inspect --format='{{.State.Status}} (exit {{.State.ExitCode}})' <container>
```

Check for:

- Missing secrets file (`pydantic.ValidationError` for a `Field(...)` with no default).
- A `.secrets-mock/` directory with the wrong permissions — production wants real secret-store mounts, not the dev mock.
- `RABBITMQ_USER`/`RABBITMQ_PASS` empty: `celery_app.py` raises `ValueError("CRITICAL: RABBITMQ credentials missing in config/env!")` at boot.

## Backups: restore drill

Every six months, run a restore test against a staging environment. The order matters:

1. Restore Postgres from the latest verified backup.
2. Restore MinIO snapshot.
3. Restore Elasticsearch snapshot — the index is rebuildable from Postgres if you lose it, but the rebuild is slow.
4. Bring up the API + workers.
5. Hit `/system/audit/verify` against the staging tenant. Should be `ok: true` (the chain was intact at backup time).

If verify fails on a fresh restore, your backup itself was already tampered with. Move further back in the backup history until you find one that verifies.
