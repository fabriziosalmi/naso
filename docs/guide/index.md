# Architecture Specification

NASO (Network Analysis and Security Operations) is engineered for high-fidelity intelligence operations. This document specifies the technical implementation of the core engine.

## Asynchronous Core

The backend is built on an event-driven architecture using **FastAPI**. All database interactions are non-blocking, utilizing the `SQLAlchemy` 2.0 asynchronous API and the `asyncpg` driver.

### Database Connection Management
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=50,
    max_overflow=100,
    pool_pre_ping=True
)
```

## Distributed Intelligence Pipeline

The ingestion engine is decoupled from the API layer to ensure horizontal scalability and fault tolerance.

### Task Orchestration
*   **Broker**: RabbitMQ.
*   **Workers**: Celery nodes configured with specific concurrency limits to optimize I/O performance during Tor crawling.
*   **Idempotency**: All processed artifacts are hashed (SHA256) to prevent duplicate analysis and storage.

## Forensic Artifact Management

### Storage Logic
*   **MinIO**: Stores raw content and full-page screenshots.
*   **Elasticsearch**: Indexes metadata and extracted snippets for sub-millisecond retrieval.

### Deletion Saga
Deleting a tenant runs a Celery saga (`tasks.maintenance.delete_tenant_saga`)
across the three stores that hold its data, in this order:

1.  Delete-by-query from Elasticsearch.
2.  Recursive bucket removal from MinIO.
3.  Relational deletes in PostgreSQL.

It is a saga, not a distributed transaction: there is no two-phase commit across
Elasticsearch, MinIO and Postgres, and a failure part-way leaves the earlier
steps done. Each step is idempotent, so the whole saga is retried — up to five
times, five minutes apart — rather than rolled back.

## AI Co-Analyst Engine

NASO utilizes local Large Language Models (LLMs) to perform automated triage and function as a proactive Co-Analyst.

### Local AI Networking & Privacy
The backend talks to any OpenAI-compatible model server — LM Studio, Ollama,
anything speaking that API. `AI_ENDPOINT` defaults to
`http://host.docker.internal:1234/v1`, the host's inference engine as seen from
inside the container, so prompts and leak content stay on your machine.

Point `AI_ENDPOINT` at a hosted API and they no longer do. Nothing in the code
prevents that — it is a URL — so if data residency is the reason you are running
NASO, that variable is the one to keep an eye on.

### Streaming Analysis & Tool Dispatch
The chat streams over Server-Sent Events. The model chooses from twelve tools,
and every one of them runs through a single dispatcher that scopes the query to
the caller's tenant:

1.  **Identities** — `search_identities`, `get_identity_insights`.
2.  **Leaks** — `get_leaks`, `find_near_duplicates`.
3.  **Reconnaissance** — `dark_web_probe`, which queues a Tor-routed Ahmia probe
    on the worker pipeline.
4.  **Investigations** — `create_task`, `flag_critical`, `toggle_identity_vip`.
5.  **Merges and audit** — `propose_merges_preview`, `get_merge_cluster`,
    `get_merge_events_history`, `verify_audit_chain`.

Tool results are rendered in the evidence panel beside the conversation, so what
the model saw is visible without taking its summary on trust.

::: warning A model reading breach text is reading untrusted input
Leak content arrives from dark-web dumps and paste sites, and it can contain
instructions aimed at the model. Tool calls stay inside the caller's tenant, so
the blast radius is bounded — but treat what the Co-Analyst tells you as a lead
to verify, not as a finding.
:::
