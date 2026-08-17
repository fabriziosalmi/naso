# API Reference

NASO exposes an asynchronous RESTful API built on FastAPI. All responses follow standard HTTP status codes and return JSON payloads.

## Authentication

Four routes answer without credentials, and no others:

| Route | Why it is open |
|---|---|
| `POST /auth/login` | how a client bootstraps a session |
| `POST /auth/logout` | takes an optional bearer and clears the cookie either way; an anonymous caller gets `200` and nothing else. It removes credentials, it never returns any |
| `GET /system/status` | orchestrators and load balancers hold no credentials, and both are written to say nothing an anonymous caller could use |
| `GET /system/health` | |

Everything else — all 46 remaining operations, `GET /ai/health` included —
requires authentication. This is not a claim from inspection:
`backend/tests/test_tenant_isolation.py` walks the OpenAPI schema and issues an
anonymous request to every documented route, failing if anything outside that
table answers, or if a guarded route rejects with anything other than `401`/`403`
(a `422` would mean the request was parsed before it was authorised).

::: warning The interactive docs are not behind auth
`/api/docs`, `/api/redoc` and `/api/openapi.json` are served to anyone who can
reach the port. They expose the full route inventory and every request schema —
no data, but a complete map. That is a reasonable default for development and a
poor one on an exposed deployment; pass `docs_url=None, redoc_url=None,
openapi_url=None` to `FastAPI()` in `backend/app/main.py`, or block the three
paths at the reverse proxy.
:::

Log in to obtain a token:

```bash
curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@naso.example.com&password=your_password"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJFZERTQSIs...",
  "token_type": "bearer"
}
```

::: tip Avoid a `.local` address
`email-validator` rejects the special-use TLDs `local`, `test`, `localhost`,
`invalid`, `arpa` and `onion`. An admin provisioned under one of them
authenticates fine and then fails response validation on `/users/me`.
`backend/init_db.py` defaults to `admin@naso.example.com` for this reason.
:::

There are two ways to present the token, and they behave differently:

**`Authorization: Bearer <access_token>`** — for API clients. Nothing else is
required.

```
Authorization: Bearer <access_token>
```

**Cookies** — for browsers. The same login response also sets `naso_access_token`
(`httpOnly`, so JavaScript cannot read it) and a `naso_csrf` companion that it
deliberately can. A cookie-authenticated request that changes state must echo
that companion back:

```
X-Naso-CSRF: <value of the naso_csrf cookie>
```

Without it the request is rejected with `403`. Safe methods are exempt, and so
is `/auth/login` itself. See [Security Model](/guide/security#csrf).

## Endpoints

### Intelligence Stream

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/leaks/` | List all leak records for the current tenant |
| `GET` | `/leaks/{id}/screenshot` | Retrieve forensic screenshot (binary) |
| `GET` | `/leaks/export/dossier` | Export full PDF dossier |
| `GET` | `/leaks/recon/darkweb?q=<query>` | Execute dark web probe via Ahmia |

### Identity Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/identities/` | List monitored identities |
| `POST` | `/identities/` | Register new identity |
| `GET` | `/identities/{id}/insights` | Deep forensic identity profile |
| `PATCH` | `/identities/{id}/protect` | Toggle VIP protection |
| `POST` | `/identities/merge` | Trigger batch auto-merge |
| `GET` | `/identities/graph` | Force-graph topology data |

### AI Co-Analyst

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/ai/health` | Check local LLM availability |
| `POST` | `/ai/chat` | Stream SSE chat with tool calling |
| `GET` | `/ai/plans` | List investigation plans |
| `POST` | `/ai/plans` | Create investigation plan |
| `PATCH` | `/ai/plans/{id}` | Update plan metadata |
| `DELETE` | `/ai/plans/{id}` | Delete investigation plan |
| `POST` | `/ai/plans/{id}/tasks` | Add task to plan |
| `PATCH` | `/ai/plans/{id}/tasks/{taskId}` | Update task status |

### System & Compliance

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/system/status` | Live database health check with latency |
| `GET` | `/system/health` | Composite readiness across every backing service |
| `GET` | `/system/audit` | Retrieve the tamper-evident audit log — `?limit=` (≤200) `&offset=` |
| `GET` | `/system/audit/verify` | Verify the hash chain; admins may pass `?tenant_id=` |
| `GET` | `/users/me` | The authenticated operator — how the SPA restores a session |
| `PUT` | `/users/me` | Update operator profile |

Both health endpoints are unauthenticated, because whatever probes them has no
credentials. They answer different questions:

- `/system/status` asks *can the API reach its database* — one probe, always
  `200`, with `"status": "operational"` or `"degraded"` in the body. This is
  what the container `HEALTHCHECK` gates on.
- `/system/health` asks *which of the five backing services is up* — database,
  Redis, Elasticsearch, MinIO and RabbitMQ, probed concurrently under a 3s
  timeout each. It answers `200` when everything configured is reachable and
  `503` when anything is not, so a load balancer can act on the status line
  alone. Each component reports `ok`, `degraded`, or `disabled` — the last for
  an optional service this deployment never configured, which is not a fault.

Neither returns hostnames, versions, or exception text. An unauthenticated
endpoint that names the host that refused a connection is a free network map;
the detail goes to the log instead.

## Token claims

Access tokens are Ed25519-signed (EdDSA) and carry `iss`, `aud`, `nbf`, `iat`,
`exp`, `jti` and `sub`. All seven are *required* on decode, and `iss`/`aud` are
matched against `JWT_ISSUER` / `JWT_AUDIENCE`, so a token minted for another
deployment sharing the same key pair is rejected rather than honoured.
`JWT_LEEWAY_SECONDS` (default 30) absorbs clock skew on the time-based claims.
Revocation is by `jti` against the Redis blacklist.

## Security Headers

The API implements strict security policies:

- **CORS**: Restricted origin policies.
- **CSRF**: Double-submit cookie — cookie-authenticated mutating requests must
  echo the `naso_csrf` cookie back in an `X-Naso-CSRF` header.
- **TrustedHost**: Drops requests with malformed `Host` headers.
- **Container Hardening**: API runs as a non-root user (uid 10001) with
  `no-new-privileges`, `cap_drop: ALL`, and a read-only filesystem.

## Interactive Documentation

When the backend is running, interactive OpenAPI documentation is available at:

- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
