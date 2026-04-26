# Security model

This page is the threat model. It covers what NASO defends against, how, and where the gaps are. Every claim links to a file or test that backs it up.

## Threat model

NASO holds (a) a graph of identifiers reconstructed from external breaches and (b) the audit trail of analysts working on it. The deployment is single-organisation, multi-tenant inside that organisation: each tenant is a customer of the SOC, and one tenant must not see another's data.

Adversaries we care about:

| Actor                                   | Capability                                          | What we expect to do                              |
|-----------------------------------------|-----------------------------------------------------|---------------------------------------------------|
| Anonymous internet                       | HTTP(S) requests, malformed payloads, port scans    | Reject without revealing internal state            |
| Authenticated tenant analyst            | Valid JWT, normal API calls                         | Strict tenant scoping; no admin routes             |
| Authenticated *admin* (cross-tenant)    | Can see everything                                  | Tamper-evident audit chain; signed dossiers        |
| Compromised browser session             | Stolen cookie via XSS                                | httpOnly cookie + CSRF + JTI revocation            |
| Cross-site form attacker                | Can trigger top-level POSTs from another origin     | CSRF double-submit cookie blocks                   |
| Local LLM provider                      | Reads anything we send                              | Run on-prem; never send raw PII to cloud LLMs      |
| SOAR receiver impersonator              | Forges critical-leak alerts to the SIEM             | HMAC-signed webhook                                |
| Spreadsheet client opening exports      | Auto-evaluates `=` cells                            | CSV cells prefixed with `'` per OWASP              |

What we **don't** defend against:

- **Compromised host / OS**: full disk encryption, SELinux/AppArmor, and the rest of the host's posture is the deployer's job. Container hardening helps but doesn't replace it.
- **Insider with shell on the DB**: tamper-evidence makes this *detectable*, not impossible. Operators must verify the audit chain regularly (see "Operating the audit chain" below).
- **Side-channel attacks on the local LLM**: if the LLM has its own outbound network access, NASO can't stop it from leaking. Network-isolate the model.

## Authentication

- **JWT EdDSA (Ed25519)**. Asymmetric — a leaked public key alone can't mint tokens. See [`shared/core/security.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/core/security.py).
- **Algorithm whitelist of one**: `algorithms=[settings.ALGORITHM]` in [`backend/app/api/deps.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/app/api/deps.py). Mitigates the alg-confusion family (`alg=none`, RS256-as-HS256).
- **Standard claims**: `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`. The decode call passes `issuer=` and `audience=` so a token signed with this server's key but for a sibling service won't be accepted on the API. Test: [`backend/tests/test_auth.py::test_token_with_wrong_audience_rejected`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_auth.py).
- **Clock-skew tolerance**: explicit `JWT_LEEWAY_SECONDS=10`. Tight default; loosen only if you actually need it.
- **Revocation via Redis JTI blacklist**. Logout adds the JTI to the blacklist with a TTL equal to the token's remaining lifetime; every authenticated request checks it. See [`shared/core/jwt_manager.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/core/jwt_manager.py).

## Cookie / CSRF

The SPA receives the JWT as an httpOnly cookie at login (so `document.cookie` can't read it; XSS can't exfiltrate). To balance that against CSRF the backend issues a second, **non-httpOnly** cookie `naso_csrf` whose value the SPA echoes in the `X-Naso-CSRF` header on every mutating request.

`CSRFMiddleware` ([`backend/app/csrf.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/app/csrf.py)) compares the two with `secrets.compare_digest` and 403s on mismatch. Skips:

- safe methods (GET/HEAD/OPTIONS)
- `/auth/login` (which mints the cookie)
- requests with no auth cookie at all (Bearer / server-to-server)

Test matrix in [`backend/tests/test_csrf.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_csrf.py).

## Tenant isolation

Every endpoint that returns or mutates tenant-scoped data filters by `current_user.tenant_id` for non-admins. Admins can see across tenants but every cross-tenant action lands in the audit chain.

- Test: `test_leaks_tenant_isolation` in [`backend/tests/test_api.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_api.py) creates two tenants and asserts a tenant-A analyst can't see tenant-B leaks.
- The merge engine has its own invariant test: `CrossTenantMerge` is raised when an attempted merge crosses a tenant boundary ([`shared/domain/services/entity_resolution.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/entity_resolution.py), test in `backend/tests/test_merge.py`).

## Audit chain (tamper-evident)

Every audit row carries `prev_hash` referring to the previous row's `self_hash`, and `self_hash = SHA256(canonical-json(everything))`. Tampering any field breaks verification from that row onward. See [`shared/utils/audit_chain.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/utils/audit_chain.py).

Concurrency:

- **In-process**: a per-tenant `asyncio.Lock` serializes the read-then-write critical section so two coroutines on the same worker can't fork the chain.
- **Cross-process** (Postgres only): `pg_advisory_xact_lock(hashtext(:tenant_id))` adds a transactional lock so two API replicas can't fork it either.

Verification: [`/system/audit/verify`](https://github.com/fabriziosalmi/naso/blob/main/backend/app/api/endpoints/system.py) walks the chain and returns `{ok, broken_at, reason, total}`. The SPA's `AuditIntegrityBanner` polls it every 5 minutes (cached locally) and shows a red bar if `ok: false`. Tests:
[`backend/tests/test_audit_chain.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_audit_chain.py) covers tamper-with-middle-row, removed-row, and 1000-write concurrent stress.

## Forensic dossier signing

Bulk PDF export goes through [`shared/utils/reporting.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/utils/reporting.py). When `NASO_PRIVATE_KEY_PATH` points at an Ed25519 / RSA PEM:

- The signer **refuses to load** keys with permissions outside `0o600` / `0o400`.
- PSS padding with SHA-256.
- The signature is returned in the `X-Forensic-Signature` response header alongside the PDF body — receivers can pin the public key and verify the dossier was generated by this NASO instance.

Without a configured key, the signer falls back to a SHA-256 hex digest. That's a tamper-evidence hint, not a real signature; production deployments should set the key.

## Container posture

- `no-new-privileges: true` on every service.
- `cap_drop: ALL` on every service.
- `read_only: true` rootfs on backend + workers, with explicit `tmpfs:` for `/tmp` and (workers) `/home/pwuser/.cache`.
- Processes run as **uid 10001** — `naso` on the API container, `pwuser` on the worker (matching the existing tmpfs path).
- Pip installs no longer pass `--trusted-host`, so the supply-chain TLS check is enforced.
- Docker Secrets pattern: passwords land in `/run/secrets/<name>` and are read by Pydantic via `secrets_dir`. The dev `.secrets-mock/` directory imitates the layout so the same code path works in compose without changes.

Reference: `Dockerfile.backend`, `Dockerfile.worker`, `docker-compose.yml`.

## Network egress

- **TLS verification on by default** for the Elasticsearch client (`ES_VERIFY_CERTS=true`) and MinIO (`MINIO_SECURE` env-driven). The dev `.env` flips ES to `false` for the self-signed dev cluster — production must remove that override.
- **HMAC-signed SOAR webhook**. Critical-severity leaks (`severity_score ≥ 90`) POST to `SOAR_WEBHOOK_URL` with `X-Naso-Timestamp` + `X-Naso-Signature-256: sha256=<hex>` over `<ts>.<body>`. The receiver should reject deliveries older than 5 minutes and `compare_digest` the MAC. Implemented in [`shared/tasks/pipeline.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/tasks/pipeline.py).
- **Tor egress isolation**. Dark-web traffic is forced through the in-cluster Tor → HAProxy chain via `TOR_PROXY`. The Ahmia client adds a circuit breaker and (optional) NEWNYM rotation per query; see [the dark-recon guide](dark-recon.md).

## Headers + browser hardening

`secure_headers_middleware` in [`backend/app/main.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/app/main.py) emits, on every response:

| Header                       | Value                                                                  |
|------------------------------|------------------------------------------------------------------------|
| `Strict-Transport-Security`  | `max-age=31536000; includeSubDomains`                                  |
| `X-Content-Type-Options`     | `nosniff`                                                              |
| `X-Frame-Options`            | `DENY`                                                                  |
| `Referrer-Policy`            | `strict-origin-when-cross-origin`                                      |
| `Permissions-Policy`         | denies accelerometer, camera, geolocation, gyroscope, magnetometer, microphone, payment, usb |
| `Content-Security-Policy`    | strict `default-src 'self'; frame-ancestors 'none'` for the API; relaxed for `/api/docs`-`/api/redoc` so Swagger UI loads from CDN |

`X-XSS-Protection` is **deliberately not set** — every modern browser ignores it, and the legacy implementations leaked cross-site information through the filter. CSP is the modern equivalent.

## Input validation

- `LeakStatus = Literal["new","reviewing","resolved","escalated","false_positive"]` ([`shared/schemas.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/schemas.py)) — anything else is rejected with 422 before the route body runs.
- `WebhookPayload` (POST `/leaks/ingest/webhook`) parsed via `model_validate_json` with `min_length` / `max_length` bounds; oversized bodies hit 413 via `Content-Length` precheck and a streamed cap.
- IP filtering on `/leaks/recon/shodan` uses Python's `ipaddress` module to reject anything that isn't a real IPv4/IPv6 address (covered by `test_shodan_rejects_invalid_ip`).
- CSV cells in both export paths (`bulk_export_leaks`, `exportAuditCsv`) are prefixed with `'` when they start with `=`/`+`/`-`/`@`/`\t`/`\r` — formula-injection mitigation per OWASP. Unit test `test_csv_safe_prefixes_dangerous_cells`.

## Operating the audit chain

The chain is self-verifying — but only if someone runs the verifier. Practical posture:

- **Banner**: keep the SPA tab open during a shift; the integrity banner polls every 5 minutes and turns red if verification fails.
- **Cron**: run `curl -s http://api/system/audit/verify | jq .ok` from your monitoring stack; alert on `false`.
- **Restore**: a broken chain is *evidence of tampering* — restore from the most recent verified backup, then walk forward through the gap to identify what the attacker touched.

## Reporting a vulnerability

Please don't open a public issue. Email the maintainer (see the `MAINTAINER` line in `pyproject.toml` if shipped, or open a private security advisory on GitHub). Allow 30 days for a fix before public disclosure.

## Known gaps

These are documented because pretending they don't exist is worse than naming them:

- **No 2FA / WebAuthn** on the operator login. Single-factor JWT only.
- **No password policy enforcement** — pyramid passes whatever bcrypt handles. Add a Pydantic `Field(pattern=...)` + zxcvbn check at user creation if your tenants need it.
- **No rate limit on the auth endpoint per username** — only per IP. A distributed credential-stuffing attempt won't be caught by slowapi alone.
- **No cursor pagination** on `/system/audit` — offset+limit is fine for hundreds of thousands of rows; redo as a keyset cursor before billions.
- **The dev `.secrets-mock/` mode is 0o755** so the non-root container user can read it through the bind mount. It's a dev-only mock; production should mount real Docker Secrets / Vault, where the secret store enforces its own ACLs.
