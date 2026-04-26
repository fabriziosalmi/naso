# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/) — major.minor.patch on the
backend API; the frontend SPA tracks the same minor.

## [1.2.0] — 2026-04-26

A hardening release. The bulk of the work is bug fixes and security controls
the README was already claiming — closing the gap between docs and code.

### Added

- **CSRF double-submit cookie protection** ([`backend/app/csrf.py`](backend/app/csrf.py)).
  The auth cookie remains httpOnly; the SPA reads a non-httpOnly `naso_csrf`
  cookie and echoes it as `X-Naso-CSRF` on every mutating request. Middleware
  enforces equality with `secrets.compare_digest`. Bearer / server-to-server
  callers are exempted automatically (no auth cookie ⇒ no browser-CSRF
  threat). Test matrix in [`backend/tests/test_csrf.py`](backend/tests/test_csrf.py).
- **Composite `/system/health` probe** across the 5 backends (PG / Redis /
  RabbitMQ / MinIO / Elasticsearch). 1 s per-probe cap; reports
  `ok | degraded | down`; opaque error strings (no hostname leakage). Auth-
  free so a load balancer can hit it without credentials.
- **HMAC-signed SOAR webhook**. Critical-severity leaks (`severity_score
  ≥ 90`) now POST `X-Naso-Timestamp` + `X-Naso-Signature-256: sha256=…` over
  `<ts>.<body>`. Receivers should reject deliveries older than 5 minutes
  and `compare_digest` the MAC.
- **Pagination + filters on `/system/audit`** — `?limit=`, `?offset=`,
  `?action=`, `?resource_type=`. Response shape changes from a bare array
  to `{total, limit, offset, items}`.
- **`GET /users/me`** for SPA session restore on refresh.
- **`/system/audit/verify` count** now uses `select(func.count())` instead
  of materializing every row into Python memory.
- **Standard JWT claims**: `iss = naso-forensic-engine`,
  `aud = naso-api`, `iat`, `nbf`, `exp`, `jti`. Verification passes
  `issuer=` / `audience=` / `leeway=` (default 10 s, env-overridable).
- **Env-driven TLS verification**: `ES_VERIFY_CERTS=true` by default
  (was hardcoded `False` in three places); `MINIO_SECURE` flag now
  propagates to every MinIO client in the codebase.
- **Env-driven `ALLOWED_HOSTS`** for `TrustedHostMiddleware`. Default
  covers localhost / docker / pytest httpx hostnames; production must
  override with the public DNS name(s).
- **Webhook ingest hardening**: `@limiter.limit("60/minute")`, 1 MiB body
  cap with `Content-Length` precheck (413 short-circuit), `WebhookPayload`
  pydantic model now actually used. Audit row written per accepted
  ingest.
- **`make bootstrap`** target. Generates `.secrets-mock/` and a working
  `.env` from `.env.example`, idempotent. Closes the gap that made
  `make up && make demo` fail on a clean clone.
- **Pre-commit hooks** (`.pre-commit-config.yaml`): ruff, hygiene,
  actionlint.
- **Security-scan workflow** (`.github/workflows/security-scan.yml`):
  pip-audit + npm audit + Trivy fs (SARIF upload), runs on PRs that
  touch dependency manifests and weekly.
- **VitePress lastUpdated footer** on every doc page.
- **Comprehensive docs**: `configuration.md`, `security.md`,
  `deployment.md`, `runbook.md`, `contributing.md`, `ai-coanalyst.md`.
- **Refreshed docs**: `architecture.md`, `dark-recon.md`,
  `identity-hub.md`, `mcp-integration.md`, `soar-and-cti.md`,
  `reporting.md`, `index.md` (now Getting Started). Every claim links
  to a file or test.

### Changed

- **README** rewritten to honest tone. Marketing language ("draconian",
  "mission-critical", "sovereign data lakes", "60-second zero-to-hero")
  removed; "What it is / What it isn't" section added; quickstart
  matches what the code actually does; every feature claim links to
  the file or test that proves it.
- **`/system/audit` response shape** is now `{total, limit, offset,
  items}` (was a bare array). Frontend store accepts both shapes for
  forward-compat with the API layer.
- **Container processes run as non-root** (uid 10001 — `naso` on the
  API container, `pwuser` on the worker, matching the existing tmpfs
  mount). Playwright's browser cache moved to `/opt/playwright`
  to survive the read-only rootfs.
- **`X-XSS-Protection` header removed** (deprecated, leaks cross-site
  information through the legacy filter). `Referrer-Policy:
  strict-origin-when-cross-origin` and `Permissions-Policy` denying
  unused browser APIs added in its place. CSP rewritten with a
  Swagger-specific relaxation so `/api/docs` actually loads.
- **CSV cells in both export paths** (`bulk_export_leaks`,
  `exportAuditCsv`) prefixed with `'` when starting with `=`/`+`/`-`/
  `@`/`\t`/`\r` (OWASP CSV-injection mitigation).
- **`LeakStatus`** is now a `Literal` closed-set
  (`new | reviewing | resolved | escalated | false_positive`).
  Endpoints accepting it return 422 on unknown values.
- **Ruff `target-version = py311`** (matches the runtime).
  `lint.ignore` trimmed from 6 entries to 3 — `B904`, `E741`, `SIM102`
  are now enforced rules. 81 fixes auto-applied; the 14 manual fixes
  cleared every remaining finding.
- **CI workflow** (`draconian-ci.yml`) refactored into 4 explicit
  parallel jobs (ruff, backend pytest, frontend vitest, docker smoke).
  Backend-container crash-loop is now detected via
  `docker inspect --format='{{.State.Status}}'` polling.
- **Worker `requirements.txt`** — dropped ghost packages
  (`rabbitmq` — not a real dep, `psycopg2-binary` — sync driver we
  don't use, `python-dotenv` — not directly imported). Conservative
  major pinning on Celery / Redis / Elasticsearch / httpx.

### Removed

- Five scratch / planning files at the repo root
  (`ROAD_TO_1000.md` + `.html`, `walkthrough.md`, `task.md`,
  `implementation_plan.md`) and `docs/NEXT_SPRINT.md`. Git history
  preserves them.
- Empty `shared/domain/models.py` (placeholder for a layer that never
  materialised).
- `pip --trusted-host pypi.org files.pythonhosted.org` from both
  Dockerfiles. Pip already trusts pypi.org via HTTPS by default; the
  flags weakened the supply chain for no benefit.
- `--trusted-host` in pip installs.

### Fixed

- **`from ..limiter import limiter`** in `backend/app/api/endpoints/auth.py`
  resolved to the non-existent `app.api.limiter`, making `app.main`
  un-importable. Three dots, not two.
- **`from ..infrastructure.rabbitmq`** in `leaks.py` — same family,
  exposed once `__init__.py` files made the package layout strict.
- **`shared/tasks/maintenance.py`** imported symbols
  (`ES_HOST`, `ES_PASSWORD`, `MINIO_*`) from `pipeline.py` that no
  longer existed there. `ImportError` at worker boot.
- **`fetchMe` SPA flow** previously called a `GET /users/me` that
  didn't exist; the resulting 405 dropped the user out of session one
  frame after a successful login. Endpoint added; `authChecked` flag
  blocks the auth gate until session restore resolves.
- **Telegram recon param** — frontend sent `channel_username`, backend
  expected `channel`. Every Telegram probe was silently 422'ing.
- **`exportMassiveDossier`** now revokes the blob URL and removes the
  synthetic `<a>` after the download.
- **Orphan e2e spec** moved from `frontend/e2e/` (outside Playwright's
  `testDir`) into `frontend/tests/e2e/`, marked skipped pending
  selector refresh — at least it's now under the matcher.
- **`generate_secrets.py`** writes `.env` populated with the same
  passwords it dropped into `.secrets-mock/*.txt`, so
  `DATABASE_URL` / `RABBITMQ_PASS` / etc. work without manual editing.
- **Hidden second copy of MinIO / OTLP / AI / SMTP / Telegram blocks**
  in `.env.example` that were producing duplicate, sometimes
  conflicting, env entries.
- **`maintenance.py` permission**: ES + MinIO clients now read TLS /
  secure flags from `Settings` instead of hardcoded `False`.
- **`backend/app/api/endpoints/leaks.py::get_leak_screenshot`** —
  refactored from inline `os.getenv` block to `Settings.MINIO_*`,
  so a production override of `MINIO_SECURE=true` actually
  propagates.
- **Logout** previously failed JWT verification on tokens minted by
  the new code path because it didn't pass `issuer=` / `audience=`.
- **20 ruff findings** cleared one-by-one across the codebase (B904,
  E741, SIM102, plus the manual UP045/UP042/SIM103 leftovers).

### Security

The full threat model now lives in [`docs/guide/security.md`](docs/guide/security.md).
Highlights of the controls landed in this release:

- CSRF, JWT iss/aud/nbf, container non-root + read-only rootfs,
  HMAC-signed outbound webhook, CSV-injection mitigation, ES + MinIO
  TLS verification on by default.
- Pip `--trusted-host` removed.
- Pre-commit + a separate weekly security workflow scanning Python /
  JS / filesystem for known CVEs.

### Migration notes

- Every existing JWT is invalidated by the new `iss` / `aud` claim
  enforcement. Users have to log in again after deploy.
- `/system/audit` response shape change is forward-compatible in the
  shipped SPA (it accepts both arrays and the new `{total, items}`
  envelope). External consumers may need an update.
- Production `ALLOWED_HOSTS` must be set explicitly to the public DNS
  name; the default no longer hard-codes "naso-api" alone.
- Production deployers should swap the dev `.secrets-mock/` bind mount
  for real Docker Secrets / Vault / SOPS — see
  [`docs/guide/deployment.md`](docs/guide/deployment.md#real-secrets).

[1.2.0]: https://github.com/fabriziosalmi/naso/releases/tag/v1.2.0
