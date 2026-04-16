# API Reference

NASO provides a robust asynchronous RESTful API built on **FastAPI** to interact with the forensic engine.

## Authentication

All API endpoints (except system health endpoints) require an **OAuth2 Bearer Token**. You must obtain a token via the `POST /auth/login` endpoint using your credentials.

```bash
# Example
curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@naso.local&password=your_password"
```

## Security Profiles

The NASO API implements Strict Security Headers natively:
- **CORS Restricted**: Hardened CORS policies.
- **TrustedHosts**: Dropping any malformed header requests.
- **Rate-Limiting**: (Coming soon) to insulate against brute force mapping.

## Key Endpoints

- `GET /ai/health` : Poll local LLM readiness.
- `POST /ai/chat`  : Stream SSE (Server Sent Events) from the AI Co-Analyst.
- `GET /leaks/` : Retrieve aggregated breaches.
- `GET /identities/` : Identity Management Hub.

> Detailed interactive OpenAPI definitions are available at `http://localhost:8000/api/docs` while the backend is running.
