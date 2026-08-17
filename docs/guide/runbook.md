# Operator Runbook

Failure modes that have actually happened on this project, what they look like
from outside, and how to resolve them. Every entry here cost someone real time.

## First moves

```bash
docker compose ps                          # what is running, what is restarting
curl -s localhost:8000/system/health | jq  # which backing service disagrees
docker compose logs --tail=60 backend
```

`/system/health` probes database, Redis, Elasticsearch, MinIO and RabbitMQ
individually and names the ones that are degraded. Start there rather than
reading logs — it turns "something is broken" into "RabbitMQ is broken" in one
request.

::: tip `docker compose logs` takes *service* names
`backend`, `worker-pipeline`, `db` — not the container names (`naso-api`,
`naso-worker-pipeline`). Compose rejects the latter with an unhelpful error.
:::

---

## The API answers, but reports `degraded`

**Symptom.** `curl localhost:8000/system/status` returns `200`, and the body
says `"status": "degraded"`. The UI loads and every data view is empty.

**Cause.** The API cannot reach Postgres. Almost always a credential mismatch:
`.env` still carries `CHANGE_ME` while Postgres was provisioned with a
generated password, or the two were generated at different times.

**Fix.**

```bash
rm .env && make bootstrap && docker compose up -d
```

`cli/generate_secrets.py` renders `.env` from `.env.example` with the generated
values substituted, precisely so the credentials the containers are provisioned
with and the ones the application connects with cannot drift apart. An existing
`.env` is deliberately left alone, so it has to be removed to be regenerated.

::: warning Never gate on the status line
`/system/status` deliberately answers `200` when degraded. If your monitoring
checks only the HTTP status, a container with a dead database reads as healthy.
Parse the body for `"operational"`.
:::

---

## A container crash-loops with `PermissionError: '/run/secrets'`

**Symptom.** The container restarts continuously. `docker exec` into it returns
in well under a second with no output, which looks like the exec failing rather
than the container being dead.

**Cause.** `.secrets-mock/` was created with restrictive permissions — a 0700
directory or 0600 files. The application containers run `cap_drop: ALL`, which
removes `CAP_DAC_OVERRIDE` and `CAP_DAC_READ_SEARCH`. Root inside such a
container **cannot** ignore file permissions the way root normally can, so a
directory it does not own and cannot traverse is simply unreadable.

This single line was the root cause of a months-long crash loop on this
project, and it presented as an exec that returned in 0.43 seconds with an
empty stdout.

**Fix.**

```bash
rm -rf .secrets-mock && make bootstrap
```

`generate_secrets.py` now writes a **0755 directory of 0444 files**, mirroring
how Docker mounts real secrets. If you write secrets by hand, match those modes.

---

## Elasticsearch crash-loops at boot

**Symptom.** `naso-search` restarts continuously. Everything else works,
because Elasticsearch is optional — which is exactly why this goes unnoticed.
`/system/health` is what tells you: it reports `elasticsearch` as `degraded`
rather than `disabled`.

**Cause, historically.** Elasticsearch reads its password from a file and
validates that file's mode, accepting only 400 or 600. The rest of
`.secrets-mock/` has to be 0444, because the application containers run
`cap_drop: ALL` and cannot read a file they do not own. Those two requirements
cannot both hold on one mounted directory.

An attempt to satisfy both — 0600 for that one file, 0444 for the rest — looked
like it worked: the `must have file permissions 400 or 600` error disappeared
and Elasticsearch loaded all its modules. It then died one step later with

```
cat: /run/secrets/elastic_password: Permission denied
```

because the entrypoint reads the file as the `elasticsearch` user, not as root.
The lesson is worth more than the fix: *the old error going away is not the
same as the thing working.* Check for a container that stays up, not for a
string that stopped appearing.

**Fix.** Elasticsearch takes `ELASTIC_PASSWORD` from `.env`, which
`make bootstrap` renders with the same value it writes into `.secrets-mock/`.
The file indirection is gone, so the conflict is gone with it. In production,
use real Docker secrets, where the orchestrator owns the file as the service
user and the conflict never arises.

**And then it failed again, differently.** With the password working,
Elasticsearch got further and hit the next wall:

```
failed to obtain node locks, tried [/usr/share/elasticsearch/data];
maybe these locations are not writable
```

`./data/elasticsearch` is created by Docker as root. Postgres and MinIO survive
the same treatment because their entrypoints start as root and chown the
directory — which is why `docker-compose.yml` grants them `CHOWN`, `FOWNER` and
`DAC_OVERRIDE`. Elasticsearch runs as uid 1000 from the start and does no such
thing. It now uses a **named volume**, which Docker initialises with the
image's own ownership.

Three distinct failures, each hidden behind the previous one, on a service that
had never once started in this stack. If you are debugging something here,
expect the same shape: fixing one error reveals the next rather than finishing
the job.

::: warning CI cannot see this
`cli/validate.sh` checks that `naso-api` is running and then runs the test
suites. Elasticsearch is optional, so it can be in a crash loop while every
check reports green. `/system/health` is what distinguishes `degraded` from
`disabled` — until something gates on it, a broken Elasticsearch is invisible
to the pipeline.
:::

---

## Postgres, Redis or RabbitMQ crash-loops immediately

**Symptom.** The datastore never reaches a healthy state; logs mention being
unable to chown the data directory or to change user.

**Cause.** `cap_drop: ALL` with nothing added back. Those images' entrypoints
start as root, chown the data directory, and drop to the service user. That
needs `CHOWN`, `SETUID`, `SETGID`, `DAC_OVERRIDE`, `FOWNER` and `SETFCAP`.

**Fix.** `docker-compose.yml` grants exactly those six capabilities to `db`,
`redis` and `rabbitmq`, with the reasoning in a comment above each. If you have
edited the file, restore them. Do not add them to `backend` or the workers —
those run application code and need none of it.

---

## Everything is up but no task ever completes

**Symptom.** Ingest and OSINT actions are accepted and stay pending forever.
The API is healthy.

**Diagnosis.**

```bash
curl -s localhost:8000/system/health | jq '.components.rabbitmq'
docker compose logs --tail=80 worker-pipeline
```

**Common causes.**

- **Broker unreachable.** Celery retries the connection quietly; the API never
  notices, because publishing succeeded into a local buffer.
- **Wrong queue.** `worker-pipeline` consumes `default` and `osint`;
  `worker-massive` consumes `massive`. A task routed to a queue nothing
  consumes sits in RabbitMQ indefinitely, visible in the management UI.
- **`worker-massive` is busy.** Concurrency is 1 by design. One long job blocks
  the queue.

---

## Dark web probes all fail or time out

**Diagnosis.**

```bash
docker compose ps | grep tor
docker compose logs --tail=40 naso-tor-1
```

**Common causes.**

- **Control-port password mismatch.** The Tor images are built with
  `TOR_CONTROL_PASSWORD` (default `naso-dev`); the workers authenticate with
  `NASO_DARKWEB_TOR_CONTROL_PASSWORD`. Change one without the other and circuit
  rotation (NEWNYM) fails while basic proxying still works — so probes
  degrade rather than stop, which makes it look intermittent.
- **Circuits still building.** Tor needs a minute or two after start before it
  will carry traffic. Failures in the first two minutes are usually not a
  fault.
- **The onion service is gone.** Common and not your problem.

---

## Shutdown hangs

**Symptom.** `docker compose down` stalls, or a container takes the full
timeout to stop.

**Cause.** `NASO_OTEL_ENABLED=true` with no collector running. The OTLP
exporter blocks at shutdown trying to flush spans to a Jaeger that is not
there.

**Fix.** Set `NASO_OTEL_ENABLED=false`, or start Jaeger:
`docker compose up -d jaeger`. The default in `.env.example` is off for exactly
this reason.

---

## The test suite passes locally and fails in the container

**Symptom.** `pytest` is green on the host; `make test` fails inside the API
container with `InvalidKeyError: Not a public or private key` on every
token operation.

**Cause, historically.** `conftest.py` used `os.environ.setdefault`. Outside a
container `ALGORITHM` is unset, so the default `HS256` applied and a string key
worked. Inside the container `.env` supplies `ALGORITHM=EdDSA`, `setdefault`
no-op'd on it, but *did* set `JWT_PRIVATE_KEY="test-secret"` — EdDSA with a
nonsense key. Fifteen tests failed only in the environment nobody ran locally.

**Fix.** `conftest.py` now mints a real ephemeral Ed25519 key pair
unconditionally, with `os.environ[...] =` rather than `setdefault`. If you add
environment setup to the test suite, set it — do not default it. The general
lesson: any test-time environment default that a real deployment might already
have set is a test that only passes where you happen to run it.

---

## CI is red and nobody changed anything

**Cause.** An unpinned tool moved. This happened with ruff: CI ran
`pip install ruff`, 0.16 started formatting Python inside Markdown fences, the
file count jumped from 107 to 122, and the gate failed on a documentation page.

**Fix.** ruff is now pinned identically in three places —
`.github/workflows/draconian-ci.yml`, `backend/requirements-dev.txt`, and
`.pre-commit-config.yaml`. They must move together. If you bump one, bump all
three in the same commit.

---

## Dependabot opened more pull requests than expected

**Cause.** `open-pull-requests-limit` is **per ecosystem**, not per repository.
This project declares seven ecosystems, so a limit of 5 permits 35 open pull
requests. The first version of the config opened sixteen at once.

**Fix.** `.github/dependabot.yml` now ignores majors everywhere, groups minors
and patches, and sets per-ecosystem limits of 1–3. Security updates are
unaffected by `ignore` rules and are still raised automatically — that is the
behaviour worth keeping.

---

## Reading a validation failure

```bash
make test        # == ./cli/validate.sh
```

Three modules run in order: backend pytest inside the API container, frontend
Vitest, Playwright end-to-end. The script prints a tally and exits non-zero on
any failure.

If it fails in **under a second with no output**, the API container is not
actually running — `docker exec` failed, not the tests. Check
`docker compose ps` before reading anything else. CI hit this for months
because it slept a fixed five seconds and then ran `docker exec` regardless;
the pipeline now waits for `/system/status` to report `operational` and dumps
every service's logs on failure.

---

## Escalating

If none of this applies, gather:

```bash
docker compose ps
curl -s localhost:8000/system/health | jq
docker compose logs --no-color --tail=100 backend worker-pipeline db
```

and open an issue with it. Redact credentials and any real identity data first
— `/system/health` deliberately returns no hostnames, but your logs might.
