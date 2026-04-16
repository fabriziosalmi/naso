# API Reference

NASO exposes an asynchronous RESTful API built on FastAPI. All responses follow standard HTTP status codes and return JSON payloads.

## Authentication

All endpoints (except system health checks) require an **OAuth2 Bearer Token** obtained via the login endpoint.

```bash
curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@naso.local&password=your_password"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Include the token in all subsequent requests:
```
Authorization: Bearer <access_token>
```

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
| `GET` | `/system/audit` | Retrieve immutable audit log |
| `PUT` | `/users/me` | Update operator profile |

## Security Headers

The API implements strict security policies:

- **CORS**: Restricted origin policies.
- **TrustedHost**: Drops requests with malformed `Host` headers.
- **Container Hardening**: API runs as a non-root user with `no-new-privileges`, `cap_drop: ALL`, and a read-only filesystem.

## Interactive Documentation

When the backend is running, interactive OpenAPI documentation is available at:

- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
