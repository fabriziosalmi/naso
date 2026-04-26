# Deployment

This page covers a real production deployment — public DNS, TLS, real secrets, backups. The dev `make up` flow stays in the README.

## Topology

```
Internet → Caddy / Traefik (TLS termination)
              │
              ├─→ React SPA (static, served by Caddy)
              │
              └─→ FastAPI backend  ──┬──── PostgreSQL (managed or self-hosted)
                                     ├──── Redis (managed)
                                     ├──── RabbitMQ (managed)
                                     ├──── Elasticsearch (cluster, 3+ nodes)
                                     ├──── MinIO (replicated, or swap for S3)
                                     ├──── Local LLM endpoint
                                     └──── Tor cluster (1+ HAProxy + N tor)
                                       │
                                       └──── Celery workers (pipeline + massive)
```

Sticky decisions:

- **Don't expose the API directly.** Always front it with a reverse proxy that does TLS, HSTS, and request-body limits. The TrustedHost middleware then locks the API to the public DNS name(s) you set in `ALLOWED_HOSTS`.
- **Single Redis vs split.** The default uses one Redis for the JWT blacklist *and* the dark-web result cache. At higher scale split them: a small ephemeral cache for dark-web, a persistent (with AOF) instance for the JWT blacklist.
- **Postgres + asyncpg.** No room here for connection-pooler-as-a-sidecar (PgBouncer in transaction mode breaks asyncpg's prepared-statement cache). Use the application pool only or run PgBouncer in *session* mode.

## Compose for prod

The bundled `docker-compose.yml` is dev-flavoured (binds source mounts, uses the mock secrets directory). For prod, layer a `docker-compose.prod.yml` override:

```yaml
# docker-compose.prod.yml
services:
  backend:
    image: ghcr.io/your-org/naso-backend:${NASO_VERSION}
    restart: always
    # Drop the source-mount; ship the baked image only.
    volumes: !reset []
    environment:
      NASO_COOKIE_SECURE: "true"
      ES_VERIFY_CERTS: "true"
      MINIO_SECURE: "true"
      ALLOWED_HOSTS: "naso.example.com,api.naso.example.com"
      ALLOWED_CORS_ORIGINS: "https://naso.example.com"
      ENVIRONMENT: "production"
    secrets:
      - jwt_private_key
      - jwt_public_key
      - db_password
      - rabbit_password
      - minio_password
      - elastic_password
      - naso_forensic_signing.pem

  worker-pipeline:
    image: ghcr.io/your-org/naso-worker:${NASO_VERSION}
    restart: always
    volumes: !reset []
    secrets:
      - jwt_private_key
      - jwt_public_key
      - db_password
      - rabbit_password
      - minio_password
      - elastic_password

secrets:
  jwt_private_key:
    external: true
  jwt_public_key:
    external: true
  db_password:
    external: true
  rabbit_password:
    external: true
  minio_password:
    external: true
  elastic_password:
    external: true
  naso_forensic_signing.pem:
    external: true
```

Run with both files:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The `external: true` flag reads the secret from the swarm/k8s/vault layer below; never put real secrets in a compose file.

## Reverse proxy (Caddy example)

```caddyfile
naso.example.com {
    encode zstd gzip

    # SPA bundle, prebuilt by `cd frontend && npm run build`.
    root * /var/www/naso/frontend/dist
    try_files {path} /index.html
    file_server

    # Anything under /api, /auth, /system, /leaks, /identities, /yara,
    # /tenants, /users, /keywords, /ai goes to the backend.
    @api {
      path /api/* /auth/* /system/* /leaks/* /identities/* /yara/* /tenants/* /users/* /keywords/* /ai/*
    }
    reverse_proxy @api naso-api:8000 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-For {remote}
        header_up Host {host}
        # Cap bodies the backend would also reject (1 MiB ingest cap).
        flush_interval -1
    }

    # Browser security headers Caddy emits in addition to what the
    # backend already sets — they apply to the SPA bundle, not just
    # the API responses.
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    }
}

api.naso.example.com {
    # Optional separate hostname for the API only — useful when the
    # SPA is hosted somewhere else (CDN, S3 + CloudFront).
    reverse_proxy naso-api:8000
}
```

Equivalent Traefik labels go in your compose file. Either way, set `NASO_COOKIE_SECURE=true` so the auth + CSRF cookies carry the `Secure` attribute (browsers refuse them otherwise on HTTPS).

## Real secrets

The dev `cli/generate_secrets.py` writes 0o644 mock files into `.secrets-mock/`. Don't ship that. Production options:

1. **Docker Swarm secrets** — `docker secret create jwt_private_key ./id_ed25519.pem`, then `external: true` in compose. Files materialise as `/run/secrets/<name>` inside the container.
2. **Vault Agent** sidecar — write secrets as files into a shared `tmpfs` volume mounted at `/run/secrets`. Pydantic-Settings picks them up automatically.
3. **SOPS-encrypted .env** in the repo + a CI step that decrypts to the deploy host. Acceptable for small teams.
4. **Cloud KMS-backed secret manager** (AWS Secrets Manager, GCP SM, Azure KV). Wire to the container via the cloud's CSI driver or a sidecar; same destination path: `/run/secrets/<name>`.

JWT keypair: rotate at least once a year, or whenever a workstation that handled it is suspected compromised. See the [Runbook](runbook.md#jwt-key-rotation).

## Database migrations

```bash
docker exec naso-api alembic upgrade head
```

For a zero-downtime deploy with a schema change, the standard flow is:

1. Deploy code that's compatible with the *old* schema.
2. Run `alembic upgrade` while the previous code is still serving.
3. Deploy code that uses the new columns.

The audit chain ([`shared/utils/audit_chain.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/utils/audit_chain.py)) imposes a constraint: never write through the legacy path while the chained writer is active, and vice versa, or you'll fork the chain. Migration `20260420_01_correlation_engine_v2.py` is the canonical example of how to backfill safely.

## Backups

Take separate snapshots; restoring NASO needs all four together:

| Store         | What to back up                               | Frequency        |
|---------------|-----------------------------------------------|------------------|
| PostgreSQL    | `pg_dump --format=custom` or PITR            | hourly + nightly |
| MinIO         | bucket-level replication or `mc mirror`      | continuous       |
| Elasticsearch | snapshot to S3 / MinIO repository            | daily            |
| `.secrets-*`  | offline copy of the JWT keypair + signing PEM | rotate-only      |

The audit chain is your authoritative truth — restore order is **Postgres first, then everything else**. If MinIO comes back before Postgres, you'll have orphan blobs whose `LeakHit` rows haven't been written.

## Resource sizing (rough)

These numbers come from a small test deployment, not from real customer traffic. Treat them as starting points.

| Service          | Memory | CPU  | Notes                                       |
|------------------|--------|------|---------------------------------------------|
| backend          | 1 GiB  | 1.0  | uvicorn, single replica handles ~150 RPS    |
| worker-pipeline  | 2 GiB  | 1.5  | YARA + Playwright; concurrency=4            |
| worker-massive   | 1 GiB  | 1.0  | Streaming bulk processor; concurrency=1     |
| postgres         | 4 GiB  | 2.0  | The audit chain + identity merge dominate   |
| elasticsearch    | 4 GiB  | 2.0  | `ES_JAVA_OPTS=-Xms2g -Xmx2g`               |
| redis            | 256 MiB| 0.5  |                                             |
| rabbitmq         | 512 MiB| 0.5  |                                             |
| minio            | 512 MiB| 0.5  | per node                                    |
| each tor + lb    | 256 MiB| 0.25 | × 5 + 1 HAProxy                             |

## Observability

- **Distributed tracing**: backend + workers emit OTLP/HTTP to `OTLP_ENDPOINT`. In dev that's the bundled Jaeger all-in-one (UI on `:16686`); in prod, point at your collector (Tempo, Honeycomb, Datadog APM, etc.).
- **Health probes**: `/system/health` returns `{status, services: {pg, redis, rabbitmq, minio, elasticsearch}}` with per-service latency. Auth-free so a load balancer can hit it without credentials.
- **Sentry**: opt-in with `SENTRY_DSN`. The frontend has its own DSN field (`VITE_SENTRY_DSN`).
- **Audit verify**: hit `/system/audit/verify` from your monitor; alert on `ok: false`.

## Updating to a new release

```bash
git fetch origin
git checkout v1.2.0           # or whatever tag
docker compose pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker exec naso-api alembic upgrade head
docker exec naso-api curl -fsS http://localhost:8000/system/audit/verify | jq .ok
```

If `audit/verify` returns `false` after the deploy, **stop the rollout** and follow the audit-chain procedure in the [Runbook](runbook.md#audit-chain-broken).
