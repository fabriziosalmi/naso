<div align="center">
  <img src="https://raw.githubusercontent.com/fabriziosalmi/naso/main/docs/public/logo.svg" width="140" alt="NASO Logo" />
  <h1>NASO Forensic Engine</h1>
  <p>
    <strong>Mission-Critical Cyber Threat Intelligence & OSINT Automation Platform</strong><br/>
    <em>High-performance data breach monitoring, AI correlation, and sovereign data lakes.</em>
  </p>

  <p>
    <a href="https://github.com/fabriziosalmi/naso/actions"><img src="https://img.shields.io/github/actions/workflow/status/fabriziosalmi/naso/draconian-ci.yml?style=for-the-badge&logo=github&color=6366f1" alt="Build Status"></a>
    <a href="https://github.com/fabriziosalmi/naso/network/members"><img src="https://img.shields.io/github/forks/fabriziosalmi/naso?style=for-the-badge&color=8b5cf6" alt="Forks"></a>
    <a href="https://github.com/fabriziosalmi/naso/blob/main/LICENSE"><img src="https://img.shields.io/github/license/fabriziosalmi/naso?style=for-the-badge&color=zinc" alt="License"></a>
  </p>
</div>

---

**NASO** is a Data-Sovereign, High-Performance Intelligence Engine built for enterprise SecOps and Red Teams. It fuses a non-blocking asynchronous architecture with Local AI (Model Context Protocol), bringing unstructured dark web telemetry into a crisp, actionable canvas.

> [!IMPORTANT]
> **Authorised and defensive use only.** NASO is a dual-use tool. It is built for
> monitoring your own organisation's exposure, incident response, and engagements
> you have written authorisation to perform. Finding a credential in a breach
> corpus does not entitle you to use it, and scanning infrastructure you do not
> own is a criminal offence in most jurisdictions.
>
> Breach data is **personal data**. If you deploy NASO you are the data
> controller under the GDPR and equivalent regimes, with everything that implies.
>
> Read **[LEGAL.md](LEGAL.md)** before pointing NASO at anything.

## Key Features

**🛡️ Hardened Container Baseline**
The API and worker containers run with `cap_drop: ALL`, `no-new-privileges:true`, and a `read_only` root filesystem. Service credentials are delivered through the Docker Secrets mechanism at `/run/secrets` rather than as environment variables. Cryptographic sessions use **EdDSA (Ed25519)** with Redis JTI blacklisting for instant token revocation.

> The shipped `docker-compose.yml` is a development and evaluation baseline, not a production configuration — it mounts generated secrets from a local directory and publishes management ports. See [SECURITY.md](SECURITY.md#operator-responsibilities) before running it against real data.

**⚡ High-Performance Ingestion API**
The ingest webhook (`POST /leaks/ingest/webhook`) uses `orjson` and `aio_pika` to stream raw unstructured data directly into RabbitMQ. Processing is decoupled from the API via Celery workers.

**🧠 Local AI with Response Caching**
Answers are cached in Redis under a SHA-256 key over the question and conversation history, so a repeated question returns without touching the model. The React frontend consumes the stream over SSE with exponential-backoff-and-jitter reconnection.

**🔍 Identity Correlation Engine**
Master identity merging clusters overlapping indicators across breach sources. Risk scoring is computed from breadth, depth, and recency of exposure. Protected (VIP) identities receive elevated monitoring.

---

## System Architecture

NASO scales horizontally. Computational workflows are offloaded into Celery pools, separating web-serving threads from forensic inferencing.

```mermaid
graph TD
    classDef intel fill:#18181b,stroke:#6366f1,stroke-width:2px,color:#FFFFFF,rx:8,ry:8;
    classDef worker fill:#09090b,stroke:#8b5cf6,stroke-width:2px,color:#FFFFFF,rx:8,ry:8;
    classDef storage fill:#18181b,stroke:#10b981,stroke-width:2px,color:#FFFFFF,rx:8,ry:8;

    A1((OSINT Feeds)):::worker
    A2((Dark Web JSON)):::worker

    B("⚡ POST /leaks/ingest/webhook"):::intel
    A1 & A2 -->|orjson + aio_pika| B

    B --> C["Message Broker\n(RabbitMQ)"]:::worker
    C --> D["Task Cluster\n(Celery Workers)"]:::worker

    D --> E{"Local LLM (Ai-Cache)\n& YARA Engine"}:::intel

    E -->|Threat Topology| F1("GraphDB & SQL\n(PostgreSQL)"):::storage
    E -->|Full-Text Index| F2("Search Engine\n(Elasticsearch)"):::storage
    E -->|Malware Payloads| F3("Object Store\n(MinIO)"):::storage
```

## Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI (async/await, SQLAlchemy 2.0 async) |
| Task Queue | Celery + RabbitMQ |
| Database | PostgreSQL 15 |
| Cache / Blacklist | Redis 7 |
| Search | Elasticsearch 8 |
| Object Storage | MinIO |
| Tracing | Jaeger (OpenTelemetry) |
| Frontend | React 18 + Vite + Zustand |
| Dark Web | Tor cluster (5 nodes) + HAProxy |
| AI | Local LLM via SSE (Ollama / LM Studio compatible) |

## Getting Started

Requirements: Docker with Compose v2, Python 3.11, Node 20.

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso

# 1. Generate the local secrets. This writes .secrets-mock/, which
#    docker-compose mounts at /run/secrets. Compose will not start without it.
python cli/generate_secrets.py

# 2. Create your .env and replace every CHANGE_ME in it.
cp .env.example .env

# 3. Bring up Postgres, Redis, Elasticsearch, MinIO, RabbitMQ, Jaeger, the
#    Tor cluster, the API, and the workers.
make up
```

The API is then on `http://localhost:8000`. **The frontend is not part of the
Compose stack** — it runs as a Vite dev server on the host:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Provision the first admin and seed synthetic data:

```bash
export NASO_ADMIN_EMAIL="admin@naso.example.com"
export NASO_ADMIN_PASSWORD="your_secure_password_here"
docker exec naso-api python init_db.py
make demo
```

> Do not give the admin an address under `.local`, `.test`, `.localhost`,
> `.invalid`, `.arpa`, or `.onion`. Those are special-use TLDs and the API's
> `EmailStr` validation rejects them, so `/users/me` would fail for that
> account.

## Environment Variables

[`.env.example`](.env.example) is the complete, annotated reference. The
variables you are most likely to touch:

| Variable | Description |
|----------|-------------|
| `NASO_ADMIN_EMAIL` | Initial admin email (default: `admin@naso.example.com`) |
| `NASO_ADMIN_PASSWORD` | Initial admin password — **required** on first run |
| `DATABASE_URL` | PostgreSQL connection string used by the application |
| `REDIS_HOST` | Redis connection URL, used for the JWT blacklist |
| `RABBITMQ_HOST` / `RABBITMQ_USER` / `RABBITMQ_PASS` | Celery broker — a worker will not start without the credentials |
| `AI_ENDPOINT` | Local LLM endpoint (e.g. `http://host.docker.internal:1234/v1`) |
| `AI_MODEL` | LLM model name (default: `gemma-4-e2b-it`) |
| `NASO_OTEL_ENABLED` | Opt in to OTLP tracing. Off by default |
| `SOAR_WEBHOOK_URL` | Optional STIX/JSON webhook fired on `severity_score >= 80` |
| `NASO_COOKIE_SECURE` | Set to `true` in production, behind HTTPS |

Note that several services take one variable to provision the container and a
different one for the application to connect with (`ELASTIC_PASSWORD` vs
`ES_PASSWORD`, `RABBIT_USER` vs `RABBITMQ_USER`, `MINIO_ROOT_USER` vs
`MINIO_ACCESS_KEY`). `.env.example` marks every such pair.

## Validation

`cli/validate.sh` runs the whole suite — backend pytest inside the API
container, frontend Vitest, and the Playwright end-to-end flow — and is what CI
runs on every pull request against `main`:

```bash
./cli/validate.sh
```

## Documentation

* [Architecture Overview](https://fabriziosalmi.github.io/naso/guide/architecture)
* [Identity Hub](https://fabriziosalmi.github.io/naso/guide/identity-hub)
* [Dark Web Recon](https://fabriziosalmi.github.io/naso/guide/dark-recon)
* [SOAR & CTI](https://fabriziosalmi.github.io/naso/guide/soar-and-cti)
* [MCP Integration](https://fabriziosalmi.github.io/naso/guide/mcp-integration)

## Roadmap

Planned hardening work is tracked in [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the
development setup, the quality bar, and the commit conventions, and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for how we expect people to behave.

One rule up front: **never contribute real data**. Fixtures, tests, and issue
reports must use synthetic values — never real personal data, real credentials,
or excerpts from a real breach corpus.

## Security

Found a vulnerability? **Do not open a public issue.** Report it privately
through a [GitHub security advisory](https://github.com/fabriziosalmi/naso/security/advisories/new)
or by email. See [SECURITY.md](SECURITY.md) for the process, scope, and safe
harbour terms — and for the hardening checklist you should work through before
running NASO against real data.

## Legal and acceptable use

NASO processes personal data and can reach systems you do not own.
[LEGAL.md](LEGAL.md) covers intended use, authorisation, prohibited uses, your
obligations as a data controller under the GDPR, third-party service terms, and
the absence of any warranty. It is not optional reading.

## License

NASO is licensed under the **[GNU Affero General Public License v3.0](LICENSE)**.

In short: you may use, study, modify, and redistribute NASO freely — but if you
run a modified version as a network service, you must make your modified source
available to its users. See the [full text](LICENSE) for the terms that actually
bind; this summary does not.

Copyright © 2026 Fabrizio Salmi.
