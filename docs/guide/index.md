# Getting Started

This page walks an analyst from a clean checkout to a working dashboard with synthetic data. Total wall time on a modern laptop: ~3 minutes (most of it pulling Docker images).

## Prerequisites

- Docker Engine 24+ with Compose v2 (`docker compose`, not the legacy `docker-compose`)
- Python 3.11 on the host (only used to run `cli/generate_secrets.py`)
- A local OpenAI-compatible LLM endpoint if you want the Co-Analyst — LM Studio, Ollama, vLLM. Optional; the rest of NASO works without it.

## 1. Bootstrap

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso
make bootstrap
```

`make bootstrap` does three things:

1. Generates an Ed25519 keypair for JWT signing.
2. Generates random passwords for Postgres, RabbitMQ, MinIO, Elasticsearch.
3. Renders `.env` from `.env.example`, substituting the placeholders.

Re-running it is a no-op (it skips existing files). Pass `--force` (or `make bootstrap-force`) if you want to regenerate from scratch — destructive on existing secrets.

## 2. Pick an admin password

```bash
export NASO_ADMIN_PASSWORD="choose-something-strong"
# Optional override (default is admin@naso.local):
export NASO_ADMIN_EMAIL="you@example.com"
```

The admin user gets created the first time `init_db.py` runs. The password is hashed (`pbkdf2_sha256`) before it ever touches Postgres; the env var is read once at seed time and forgotten.

## 3. Start the stack

```bash
make up           # docker compose up -d
docker exec naso-api python init_db.py
```

What you should see:

| Container             | Status      | Notes                                            |
|-----------------------|-------------|--------------------------------------------------|
| `naso-db`             | healthy     | Postgres 15                                      |
| `naso-cache`          | running     | Redis                                            |
| `naso-search`         | healthy     | Elasticsearch (takes ~30s to settle)             |
| `naso-storage`        | running     | MinIO                                            |
| `naso-broker`         | healthy     | RabbitMQ                                         |
| `naso-jaeger`         | running     | OTel collector + Jaeger UI on :16686             |
| `naso-api`            | running     | FastAPI                                          |
| `naso-worker-pipeline`| running     | Celery worker (default + osint queues)           |
| `naso-worker-massive` | running     | Celery worker (massive queue)                    |
| `naso-tor-1..5`       | running     | Tor cluster                                      |
| `naso-tor-cluster`    | running     | HAProxy in front of the Tor cluster              |

If anything is `Restarting`, jump to the [Runbook → triage map](runbook.md#triage-map).

## 4. Seed demo data (optional)

```bash
make demo
```

Loads "Operation Lazarus": one tenant, ~30 identities (3 VIPs + dev/HR/contractor cohorts), and a couple hundred leak hits across GitHub / Pastebin / dark-web / Telegram / Shodan sources. The dashboard becomes useful to look at.

## 5. Open the dashboard

```bash
open http://localhost:5173
```

Log in with the admin email + password you set in step 2. First-login UI:

- **Dashboard** — overall posture, severity histogram, recent leaks.
- **Identities** — the master-identity graph, with the merge-preview drawer behind `Cmd+K → "Preview merges"`.
- **Topology** — force-directed network of identities ↔ leaks. Heavy; pages of 500 nodes by default.
- **Dark Search** — interactive Ahmia probe. Output includes per-result provenance (page, fetched_at, via_tor flag).
- **Audit** — paginated audit chain view with the integrity verification status banner.
- **AI Co-Analyst** — chat surface, only useful when `AI_ENDPOINT` actually points at a running LLM.
- **Docs** — this site, embedded.

## Where to go next

- [Architecture](architecture.md) for the runtime layout.
- [Configuration](configuration.md) for every environment variable.
- [Security](security.md) for the threat model and what the controls actually defend against.
- [Deployment](deployment.md) when you're past dev and need TLS, real secrets, backups.
- [Runbook](runbook.md) for on-call.

If something didn't work above, the Runbook's triage map is the fastest route to the cause.
