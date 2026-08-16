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
> The version strings in the codebase disagree with each other today
> (`backend/app/main.py` says `1.1.0`, `frontend/package.json` says `0.1.0`,
> `docs/package.json` says `1.0.0`). Unifying them is a deliberate change that
> belongs with the first tagged release, not a silent edit here.

## [Unreleased]

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

### Security

Findings closed in this cycle: CSRF on all cookie-authenticated mutating
endpoints; unscoped JWT acceptance; root execution inside the application
containers; unverified PyPI certificates during image build; a hardcoded
database credential; a seeded admin password. Reporting instructions and
supported-version policy are in [SECURITY.md](SECURITY.md).

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
- Compliance layer — hash-chained immutable audit log with an integrity
  verification endpoint, CSV export, and PDF dossier generation.
- Multi-tenancy with tenant isolation enforced at the query level.
- SOAR and CTI handoff hooks, YARA rule evaluation, MITRE ATT&CK technique
  seeding.
- Observability: OpenTelemetry tracing through Jaeger.
- Test infrastructure: pytest for the backend, Vitest for the frontend store,
  Playwright for end-to-end flows, and `cli/validate.sh` as the structural gate.

[Unreleased]: https://github.com/fabriziosalmi/naso/commits/main
