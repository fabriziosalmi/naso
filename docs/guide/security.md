# Security Model

What NASO defends against, how, and — equally important — what it does not
defend against. To report a vulnerability, see
[SECURITY.md](https://github.com/fabriziosalmi/naso/blob/main/SECURITY.md).

## Threat model

NASO holds breach data, dark web telemetry, and identity records about people
who did not consent to being in your database. The assets worth protecting, in
order:

1. **The data itself.** A NASO instance is a concentrated collection of exactly
   the material an attacker would otherwise have to assemble.
2. **Tenant isolation.** One customer reaching another customer's records is
   the failure that ends the deployment.
3. **The audit trail.** If it can be altered, nothing else it says is evidence.
4. **The outbound integrations.** Tor, Shodan, Telegram and SOAR webhooks all
   reach the network from inside your perimeter.

Assumed adversaries: an authenticated operator escalating beyond their tenant
or role; an unauthenticated attacker who can reach the API; a malicious payload
in ingested data, including prompt injection aimed at the AI Co-Analyst; and
whoever finds the deployment on the public internet because a port was left
open.

Explicitly **not** in the model: a compromised host, a malicious administrator,
and denial of service by volume.

## Authentication

Sessions are Ed25519-signed JWTs (`EdDSA`). The private key never leaves the
API container; the worker fleet does not mint tokens.

**Claims.** Every token carries `iss`, `aud`, `nbf`, `iat`, `exp`, `jti` and
`sub`. All seven are *required* on decode, and `iss`/`aud` are matched against
`JWT_ISSUER`/`JWT_AUDIENCE`. Without that check, any token signed by the same
key pair is honoured — including one minted for a different deployment, or by
a sibling service that happens to share the key. `JWT_LEEWAY_SECONDS` (30 by
default) absorbs clock skew on the time-based claims, so a fleet with imperfect
NTP does not produce intermittent 401s that look like an auth bug.

Every decode goes through one function, `decode_access_token` in
`shared/core/security.py`. Call sites do not pass their own argument set to
`jwt.decode` — that divergence is how one endpoint ends up verifying the
audience and another does not.

**Revocation.** Logout blacklists the token's `jti` in Redis with a TTL equal
to the token's remaining lifetime, so the entry expires exactly when the token
would have. Every authenticated request checks it.

**Transport.** The token is delivered as an `httpOnly` cookie so JavaScript
cannot read it, which is what makes an XSS bug in the frontend non-fatal to the
session. `Bearer` headers are also accepted, for API clients that are not
browsers.

::: warning Set `NASO_COOKIE_SECURE=true` in production
The default is `false` so the stack works over plain HTTP on localhost. Left at
`false` behind TLS, the session cookie is sent over any downgraded connection.
:::

## CSRF

Cookie authentication means the browser attaches credentials to cross-origin
requests automatically. Without a second factor, every mutating endpoint is
reachable from any page the operator has open.

NASO uses the **double-submit cookie** pattern:

- On login the API sets `naso_csrf` — a random token, deliberately *not*
  `httpOnly`, alongside the `httpOnly` session cookie.
- The SPA reads it with `document.cookie` and echoes it back in an
  `X-Naso-CSRF` header on every mutating request (an axios request
  interceptor does this globally).
- `CSRFMiddleware` compares the two with `secrets.compare_digest` and rejects
  a mismatch with `403`.

The check is skipped in three cases, each deliberate:

| Case | Why |
|---|---|
| Safe methods (`GET`, `HEAD`, `OPTIONS`) | No state change to protect. |
| No session cookie present | A `Bearer` client supplies its credential explicitly; there is no browser-CSRF threat to answer. |
| `POST /auth/login` | The SPA cannot bootstrap a session otherwise. |

An attacker's page can *cause* a cross-origin request, but cannot read the
victim's cookies to learn the token — that is the property the whole pattern
rests on, and it is why `SameSite=lax` alone is not treated as sufficient.

## Authorization and tenancy

Every record carries a `tenant_id`, and queries filter on the tenant embedded
in the caller's token rather than on anything the caller supplies. Two roles
exist: `analyst` and `admin`; `check_admin` gates administrative routes.
Admins can read across tenants — a deliberate choice for a single-operator
deployment, and one to revisit before offering NASO as a hosted multi-customer
service.

## Audit trail

Every operator- and AI-initiated action is written to a hash-chained audit log:
each row commits to its predecessor, so an inserted, deleted or edited row
breaks the chain from that point on. `GET /system/audit/verify` walks it and
reports the first break with a row identifier. This detects tampering; it does
not prevent it. An attacker with write access to Postgres can rewrite the chain
wholesale. Ship the log somewhere append-only if that matters to you.

## Container hardening

| Control | API | Workers | Datastores |
|---|---|---|---|
| Non-root user | uid 10001 (`naso`) | uid 10001 (`pwuser`) | image default |
| `cap_drop: ALL` | ✅ | ✅ | ✅ |
| `cap_add` | *(none)* | *(none)* | see below |
| `no-new-privileges` | ✅ | ✅ | ✅ |
| `read_only` root filesystem | ✅ | ✅ | ❌ (they write data) |
| Writable paths | `/tmp` | `/tmp`, `/home/pwuser/.cache` | volumes |

Postgres, Redis and RabbitMQ add back `CHOWN`, `SETUID`, `SETGID`,
`DAC_OVERRIDE`, `FOWNER` and `SETFCAP`. Their official entrypoints need those
to chown the data directory and drop from root to the service user; without
them the containers crash-loop. This is declared in `docker-compose.yml` with
the reason next to it rather than hidden in an override file — a capability
grant you cannot see is one you cannot audit.

Neither image installs from PyPI with certificate verification disabled. The
`--trusted-host` flags that used to be in both Dockerfiles are gone.

## Automated scanning

`.github/workflows/security-scan.yml` runs on every push and pull request and
weekly on a schedule:

| Scanner | Target | Fails on |
|---|---|---|
| `pip-audit` | the three Python requirement sets | any known advisory |
| `npm audit` | `frontend/`, `docs/` | `high` and above |
| Trivy | both container images | `HIGH`/`CRITICAL` **with a fix available** |
| Gitleaks | the working tree | any credential pattern |

The weekly run is the one that matters — an advisory against a transitive
dependency lands without anyone touching the repository.

## AI-specific risk

The Co-Analyst reads attacker-supplied text: leak contents, dark web page
bodies, Telegram messages. Anything it reads can attempt prompt injection.
Mitigations in place:

- the toolkit is a fixed allow-list, not a general code executor;
- destructive operations are not exposed as tools — the model can flag, tag and
  propose, but not delete;
- every tool call is written to the audit log with its arguments, so an
  injection that succeeds is visible afterwards;
- tool calls execute with the calling operator's tenant and role, so an
  injected instruction cannot reach data the operator could not reach.

This narrows the blast radius; it does not eliminate the class. Treat AI output
as a lead, not a finding. See [AI Co-Analyst](/guide/ai-coanalyst).

## Known gaps

Stated plainly, because a security page that lists only strengths is marketing:

- **No 2FA or SSO.** Password plus JWT is the whole authentication story.
- **No field-level encryption.** Data is protected at rest only by whatever
  encrypts the Postgres volume.
- **Admins cross tenants** — see above.
- **The audit chain detects tampering, it does not prevent it.**
- **Rate limiting is per-process and in-memory.** Behind more than one API
  replica the effective limit multiplies by the replica count.
- **`docker-compose.yml` is an evaluation baseline, not a production
  configuration.** It publishes management interfaces and terminates no TLS.

## Operator checklist

Before pointing NASO at real data:

1. `make bootstrap`, and never reuse the values from `.env.example`.
2. `NASO_COOKIE_SECURE=true`, with TLS terminated in front of the API.
3. `ALLOWED_CORS_ORIGINS` restricted to the real frontend origin.
4. `JWT_ISSUER`/`JWT_AUDIENCE` unique to this deployment.
5. Jaeger (`16686`), the MinIO console and RabbitMQ management off any
   untrusted network.
6. Tor images rebuilt with your own control-port password —
   `docker compose build --build-arg TOR_CONTROL_PASSWORD=<strong-pw>`, matched
   by `NASO_DARKWEB_TOR_CONTROL_PASSWORD` on the workers.
7. Real Docker secrets or a secret manager mounted at `/run/secrets`, not
   `.secrets-mock/`.
8. Read [LEGAL.md](https://github.com/fabriziosalmi/naso/blob/main/LEGAL.md).
   The database contains personal data and that has consequences independent of
   how well it is secured.
