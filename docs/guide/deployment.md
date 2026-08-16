# Deployment

## What you are deploying

Eleven services. Five of them are stateful and will lose data if you treat
their volumes as disposable.

| Service | Image | Role | Stateful |
|---|---|---|---|
| `backend` | built from `Dockerfile.backend` | FastAPI API, port 8000 | no |
| `worker-pipeline` | built from `Dockerfile.worker` | Celery, queues `default` + `osint` | no |
| `worker-massive` | built from `Dockerfile.worker` | Celery, queue `massive`, concurrency 1 | no |
| `db` | `postgres:15-alpine` | primary store | **yes** |
| `redis` | `redis:7-alpine` | JWT revocation list, cache | **yes** |
| `rabbitmq` | `rabbitmq:3-management-alpine` | Celery broker | **yes** |
| `elasticsearch` | `elasticsearch:8.12.0` | full-text search *(optional)* | **yes** |
| `minio` | `quay.io/minio/minio` | artifact storage *(optional)* | **yes** |
| `jaeger` | `jaegertracing/all-in-one:1.53` | tracing *(optional)* | no |
| `naso-tor-1..n` | built from `infrastructure/tor` | Tor circuits | no |
| `naso-tor-lb` | `haproxy:alpine` | load-balances the Tor cluster | no |

Elasticsearch and MinIO are genuinely optional: with their credentials unset,
no client is constructed and `/system/health` reports them as `disabled`.

## Evaluation deployment

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso
make bootstrap        # generates .secrets-mock/ and renders .env
make up               # docker compose up -d
```

Then wait for the API to report ready — not merely to answer:

```bash
curl -s localhost:8000/system/status | jq -r .status   # want: operational
```

::: danger `/system/status` answers 200 even when degraded
It returns `200` with `{"status": "degraded"}` when the database probe fails,
so that a monitoring system gets a body it can reason about rather than a bare
connection error. Anything gating on the status line alone will call a
container with a dead database healthy. The container `HEALTHCHECK` and the CI
readiness gate both parse the body; yours should too.
:::

Seed synthetic data if you want something to look at:

```bash
make demo             # 'Operation Lazarus'
```

The frontend dev server runs separately:

```bash
cd frontend && npm ci && npm run dev      # http://localhost:5173
```

## Ports

Only `8000` is published by default from the application side. Jaeger publishes
`16686` (UI), `4317` and `4318` (OTLP). The datastores are reachable only on
the internal `naso-net` network.

::: warning Publishing more
If you add port mappings for Postgres, RabbitMQ management or the MinIO
console, put them behind a firewall or a VPN. RabbitMQ management and the
MinIO console are full administrative interfaces.
:::

## Production changes

`docker-compose.yml` is an evaluation and development baseline. It is not a
production configuration, and it does not pretend to be. Before real data:

**Secrets.** Replace the `.secrets-mock/` bind mount with real Docker secrets
or a secret manager mounted at `/run/secrets`. Remember that a value in `.env`
takes precedence over a file in `/run/secrets` — see
[Configuration](/guide/configuration#where-values-come-from).

**TLS.** Terminate in front of the API. Set `NASO_COOKIE_SECURE=true` and
restrict `ALLOWED_CORS_ORIGINS` to the real frontend origin.

**Images.** Build with the default `INSTALL_DEV=false`. The Compose file sets
`INSTALL_DEV: "true"` so that `cli/validate.sh` can run the test suite inside
the running container; a production image should not ship pytest.

```bash
docker build -f Dockerfile.backend -t naso-backend:1.0.0 .
docker build -f Dockerfile.worker  -t naso-worker:1.0.0  .
```

**Tor.** Rebuild with your own control-port password. The default is `naso-dev`
and is documented, which means it is public:

```bash
docker compose build --build-arg TOR_CONTROL_PASSWORD=<strong-pw>
```

Set `NASO_DARKWEB_TOR_CONTROL_PASSWORD` on the workers to the same value; they
must be changed together or circuit rotation stops working.

**Resource limits.** The Compose file sets 1 CPU / 1 GB for the API, 1.5 / 2 GB
for `worker-pipeline` and 1 / 1 GB for `worker-massive`. `worker-massive` runs
at concurrency 1 by design — it handles jobs whose memory footprint scales with
input size.

**Admin provisioning.** `backend/init_db.py` refuses to create the initial admin
unless `NASO_ADMIN_PASSWORD` is set. There is no default and no fallback. Avoid
a `.local` domain in `NASO_ADMIN_EMAIL`: `email-validator` treats it as a
special-use TLD and the account will fail response validation on `/users/me`.

## Non-root containers

Both application images run as uid 10001. Two things follow that are easy to
trip over when you customise them:

- **The root filesystem is read-only.** `/tmp` is a tmpfs; the workers also get
  `/home/pwuser/.cache`. Anything that needs to write elsewhere fails, by
  design. If you add a component that writes to disk, give it a volume
  explicitly rather than relaxing `read_only`.
- **Playwright browsers live in `/opt/playwright`**, not `~/.cache/ms-playwright`.
  `playwright install --with-deps` runs as root at build time, so the default
  location would be unreadable to `pwuser` — and `/home/pwuser/.cache` is a
  tmpfs at runtime, which would mask anything installed there anyway.

## Upgrading

1. Read [CHANGELOG.md](https://github.com/fabriziosalmi/naso/blob/main/CHANGELOG.md).
2. Back up the Postgres volume. NASO is pre-1.0; migrations are forward-only.
3. `docker compose pull && docker compose build`
4. `docker compose up -d`
5. Confirm with `curl -s localhost:8000/system/health | jq`.

Alembic migrations live in `backend/alembic/`.

## Verifying a deployment

```bash
make test        # delegates to cli/validate.sh
```

`cli/validate.sh` is the same script CI runs, in the same order: backend pytest
inside the API container, frontend Vitest, and Playwright end-to-end flows. It
prints a module tally and exits non-zero on any failure. If it passes, the
stack works — not merely starts.
