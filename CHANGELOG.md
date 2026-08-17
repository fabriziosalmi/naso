# Changelog

Notable changes to NASO, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) — with the caveat
that NASO is pre-1.0 and the public API may change in a minor release.

> **A note on the history below.** This file starts at the public-readiness
> work. The 51 commits before it were never tagged, and reconstructing release
> boundaries after the fact would produce a fiction that looks like a record.
> What is there instead is an honest summary of where the project stood when
> this file was written; `git log` is the authority for anything earlier.
>
> The version strings in the codebase used to disagree with each other
> (`backend/app/main.py` said `1.1.0`, `frontend/package.json` `0.1.0`,
> `docs/package.json` `1.0.0`) because nothing had ever been released and each
> had been bumped on its own occasion. They are unified at **0.1.0** with this,
> the first tagged release. `0.x` is the honest number: this file has said the
> project is pre-1.0 since the day it was written, and a `1.x` tag promises API
> stability nobody here is in a position to keep. The version rises to `1.0.0`
> when the HTTP API stops changing shape, not when the code feels finished.

## [0.1.2] — 2026-08-18

### Fixed

- **Two of the application's own pages were unreachable by URL.** The dev and
  preview proxy matched API prefixes by string prefix, so `/ai` swallowed
  `/ai-analyst` and `/identities` collided exactly. A reload, a bookmark or a
  shared link to either rendered `{"detail":"Not Found"}` from the API instead
  of the application. All seven routes are now covered by a test that loads them
  directly.
- Three more claims the interface made and the code does not support: the
  "Ahmia Active · Tor Circuit On · Correlation On" dots under the dark-web probe
  (wired to nothing, and *On* throughout the Tor crash loop); "Immutable
  forensic accountability — every operation hashed and logged" on the audit page
  (tamper-evident, not immutable; authentication is not audited; legacy rows
  carry no hash); and an in-app API reference with a wrong Telegram parameter, a
  stale audit description, and two missing routes.

## [0.1.1] — 2026-08-18

Everything here was found by driving the interface in a browser after 0.1.0 was
tagged, and none of it was visible from the code or from the test suite.

### Fixed

- **The interface stopped inventing what it reports.** A hardcoded array of
  seven log lines displayed at random under *System Logs* — including an
  invented YARA match count and the author's own name — now tails the real audit
  log. `Cluster #Alfa-7`, a `'0.42'` fallback for database latency, four
  constant service-status rows on the login screen, and a constant
  `Infrastructure Load` percentage are gone; the login screen reads the
  unauthenticated `/system/health` instead, and the dashboard card reports
  unacknowledged criticals, which the data can answer.
- **The sidebar had no styling at all.** `NavLink` inside `Tooltip.Trigger
  asChild` had its function `className` stringified by Radix's Slot, so every
  navigation item rendered as a bare inline anchor.
- **The dashboard never loaded data.** `isAuthenticated` was missing from the
  fetch effect's dependency array, so with a full database the dashboard showed
  its empty state and a reload repeated the race.
- **The session probe logged you out.** A 401 from `GET /users/me` — the correct
  answer for an anonymous browser — triggered the global interceptor's logout.
- **The audit verifier stopped accusing.** Rows predating the hash chain were
  reported as `row content tampered`; they are counted as `legacy_unhashed` and
  skipped, and deliberately not back-filled.
- **The MCP server** shape-checks its tenant id, orders explicitly and clamps a
  model-supplied limit.

### Added

- `frontend/demo/record.mjs` — the scripted walkthrough that found all of it.
- Open Graph card, sitemap and a meta description for the documentation site.

## [0.1.0] — 2026-08-17

First tagged release. Everything below happened before the tag; the sections
are grouped by what changed rather than by which pull request changed it.

The work required before this repository could be published. Five items each
blocked publication on their own.

### Added

- **Licence.** AGPL-3.0-only. NASO is a network service that processes other
  people's personal data; a licence that lets a hosted fork keep its
  modifications private is the wrong one for this project.
- **Community and governance files** — `SECURITY.md` with a private disclosure
  channel, safe-harbour terms and an explicit operator-responsibility list;
  `CONTRIBUTING.md`; `CODE_OF_CONDUCT.md`; `LEGAL.md` covering the data
  protection obligations that come with running this; issue and pull-request
  templates; a Dependabot configuration.
- **CSRF protection** — double-submit cookie. The API authenticates by
  `httpOnly` cookie, which means the browser attaches credentials to
  cross-origin requests automatically; without this, every mutating endpoint
  was reachable from any page the operator happened to have open. Mutating
  requests authenticated by cookie must echo the `naso_csrf` cookie in an
  `X-Naso-CSRF` header. Bearer-token clients are unaffected — there is no
  browser-CSRF threat when the caller supplies the credential explicitly.
- **`GET /system/health`** — composite readiness across database, Redis,
  Elasticsearch, MinIO and RabbitMQ, probed concurrently under a per-probe
  timeout. Answers `200`/`503` so a load balancer can act on the status line,
  and reports each component as `ok`, `degraded` or `disabled`. Unauthenticated
  and deliberately terse: no hostnames, versions or exception text.
- **`Security Scan` workflow** — pip-audit, npm audit, Trivy and Gitleaks, on
  every push and pull request and weekly on a schedule. Separate from the merge
  gate on purpose; see `SECURITY.md`.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff pinned to the same
  version CI installs, plus secret detection, large-file and parse checks.
- **`make bootstrap`** — one target that generates secrets and renders `.env`,
  so the command the README gives a new user is the same one CI runs, and a
  break in it fails the build rather than only failing them.

### Changed

- **Containers run as a non-root user.** Both application images now run as uid
  10001 — `naso` in the API image, `pwuser` in the worker — alongside the
  `cap_drop: ALL`, `no-new-privileges:true` and `read_only: true` that were
  already in place. Playwright browsers moved to `/opt/playwright` so the
  non-root user can reach them.
- **JWT tokens are scoped to the deployment.** Tokens now carry `iss`, `aud`
  and `nbf` alongside `iat`/`exp`/`jti`/`sub`, all seven are required on
  decode, and `iss`/`aud` are verified against `JWT_ISSUER`/`JWT_AUDIENCE`.
  Previously `jwt.decode` was called with only the key and the algorithm, so
  any token signed by that key pair was honoured — including one minted for a
  different deployment sharing it. `JWT_LEEWAY_SECONDS` (default 30) absorbs
  clock skew.
- **Secret generation is Docker-shaped.** `cli/generate_secrets.py` writes
  `.secrets-mock/` as a 0755 directory of 0444 files, mirroring how Docker
  mounts real secrets, and renders `.env` from `.env.example` with the
  generated values substituted. The previous 0700/0600 layout was unreadable
  by a `cap_drop: ALL` container, which has no `CAP_DAC_OVERRIDE` and so cannot
  ignore file permissions — that single line was the root cause of a
  months-long crash loop.
- **Datastore capabilities are declared, not worked around.** `db`, `redis` and
  `rabbitmq` keep `cap_drop: ALL` but add back `CHOWN`, `SETUID`, `SETGID`,
  `DAC_OVERRIDE`, `FOWNER` and `SETFCAP`. Their official entrypoints need those
  to chown the data directory and drop from root to the service user. This was
  previously hidden in an opt-in override file; it belongs in the open, with
  the reason next to it.
- **`--trusted-host pypi.org --trusted-host files.pythonhosted.org` removed**
  from both Dockerfiles. Those flags disable certificate verification for the
  channel that installs the code being run.
- **CI is green, and means something.** The readiness gate parses the
  `/system/status` body rather than its status line, because that endpoint
  answers `200` with `"degraded"` when the database probe fails — the previous
  check would have passed a container with a dead database. Diagnostics run
  with `if: always()`, so a failure is explained rather than guessed at.
- **Ruff is pinned** to one version across CI, `requirements-dev.txt` and the
  pre-commit hook. An unpinned `pip install ruff` turned the gate red on a day
  nobody had touched the code, when 0.16 began formatting Python inside
  Markdown fences.
- **Test suite runs against the algorithm production uses.** `conftest.py`
  mints an ephemeral Ed25519 key pair unconditionally instead of calling
  `setdefault` on the environment. The old form silently fell back to HS256
  outside a container and left `ALGORITHM=EdDSA` with a nonsense key inside
  one, so fifteen tests passed locally and failed in CI.

### Fixed

- A hardcoded database password in `shared/tasks/maintenance.py`.
- `backend/init_db.py` seeding a known admin password; it now requires
  `NASO_ADMIN_PASSWORD` and refuses to provision without it.
- `NASO_OTEL_ENABLED=true` in `.env.example` while no collector runs by
  default, which reinstated a shutdown hang.
- Missing `__init__.py` across `backend/app`, `backend/app/api`,
  `backend/app/api/endpoints` and `cli`.

#### Found by running the stack on a real Docker daemon

Everything above was verified in CI only. The first local run found four things
CI could not see, because the pipeline started seven of the fifteen containers
`make up` starts and `cli/validate.sh` checked exactly one of them.

- **The Tor cluster had never started.** All six containers were in a permanent
  restart loop: `tor` ran as root against a `/var/lib/tor` owned by the `tor`
  user and refused it, and haproxy then aborted at boot because the instance
  names would not resolve. The balancer now tolerates missing backends
  (`init-addr last,libc,none`), which is what makes five instances a cluster
  rather than five single points of failure.
- **The application had never reached Elasticsearch.** Three call sites and the
  container healthcheck spoke `https` to a node that serves plaintext with Basic
  auth, so `/system/health` reported `elasticsearch: degraded` and `naso-search`
  sat `(unhealthy)` for its entire life. One client factory now owns the scheme
  (`ES_USE_TLS`) and passes the credential as `basic_auth=` rather than in the
  URL, where the tracing instrumentation would have recorded it.
- **Migrations had never run, and could not.** `create_all` never alters an
  existing table, `PYTHONPATH=/app` plus a directory named `alembic` shadowed
  the package so the CLI could not start, and the models had drifted past the
  one migration that existed. `init_db.py` now runs `alembic upgrade head`, the
  tree lives in `backend/migrations/`, and `20260817_02_ack` closes the drift.
- **`make demo` had never run.** It imported a name that does not exist, and
  once fixed, failed on a second invocation because it inserted a tenant whose
  name is unique. Both fixed; the seed is idempotent.

#### Found by the fourth adversarial pass

- **Every page reload signed the operator out.** `GET /users/me` did not exist —
  only `PUT` — while the SPA's session probe called it and nothing called the
  probe. Moving the token to an `httpOnly` cookie removed the SPA's only way to
  see its own session and nothing replaced it.
- **CSV export wrote formulas.** Values arriving from dark-web dumps and the
  ingest webhook were written verbatim, so `=cmd|…` in a leak `source` executed
  when an analyst opened the export (CWE-1236).
- **`GET /system/audit/verify?tenant_id=` was documented and ignored**, quietly
  answering about the caller's own tenant. `/system/audit` gained paging.

### Security

Findings closed in this cycle: CSRF on all cookie-authenticated mutating
endpoints; unscoped JWT acceptance; root execution inside the application
containers; unverified PyPI certificates during image build; a hardcoded
database credential; a seeded admin password; a cross-tenant write on
`PATCH /ai/plans/{id}/tasks/{taskId}`; an unauthenticated, verbose `/ai/health`;
spreadsheet formula injection in the CSV export; an unlimited ingest webhook;
and an Alpine package feed downgraded to plain HTTP in the Tor image.
Reporting instructions and supported-version policy are in
[SECURITY.md](SECURITY.md).

## Prior history (April 2026 – July 2026, untagged)

Summarised, not reconstructed. Roughly in the order it happened:

- Initial platform: FastAPI backend, React 18 + Vite frontend, Celery workers
  on RabbitMQ, Postgres, Redis, Elasticsearch, MinIO.
- Identity Hub — identity correlation with an auto-merge algorithm, a
  reversible merge ledger, and a force-directed topology graph.
- Dark web reconnaissance over a Tor cluster behind HAProxy, with NEWNYM
  circuit rotation and an Ahmia gateway.
- OSINT integrations: Shodan and zero-auth Telegram channel interception.
- AI Co-Analyst — SSE-streamed chat with tool calling, MCP server, investigation
  plans and tasks.
- Compliance layer — hash-chained, tamper-evident audit log with an integrity
  verification endpoint, CSV export, and PDF dossier generation.
- Multi-tenancy with tenant isolation enforced at the query level.
- SOAR and CTI handoff hooks, YARA rule evaluation, MITRE ATT&CK technique
  seeding.
- Observability: OpenTelemetry tracing through Jaeger.
- Test infrastructure: pytest for the backend, Vitest for the frontend store,
  Playwright for end-to-end flows, and `cli/validate.sh` as the structural gate.

[0.1.2]: https://github.com/fabriziosalmi/naso/releases/tag/v0.1.2
[0.1.1]: https://github.com/fabriziosalmi/naso/releases/tag/v0.1.1
[0.1.0]: https://github.com/fabriziosalmi/naso/releases/tag/v0.1.0
