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
The deletion of a tenant triggers a distributed transaction that ensures data consistency across all storage engines:
1.  Query and delete indices from Elasticsearch.
2.  Recursive bucket removal from MinIO.
3.  Relational record pruning in PostgreSQL.

## AI Co-Analyst Engine

NASO utilizes local Large Language Models (LLMs) to perform automated triage and function as a proactive Co-Analyst.

### Local AI Networking & Privacy
The platform connects to any OpenAI-compatible local AI model server (e.g., LM Studio, Ollama). By default, the system leverages `host.docker.internal:1234/v1` to tunnel from the Dockerized NASO backend to the host's inference engine — ensuring zero data leakage to third parties.

### Streaming Analysis & Tool Dispatch
The NASO Co-Analyst uses Server-Sent Events (SSE) to provide an immediate, reactive chat experience directly in the unified interface. The backend continuously evaluates the context of the analyst's inquiries to dispatch real-time tool executions:

1.  **Identity Queries** (`search_identities` / `get_identity_insights`): Looks up high-risk profile fragments, unifying names and evaluating historical severity scores.
2.  **Dataset Interrogation** (`get_leaks`): Performs filtered lookups against intercepted dumps from external platforms (e.g., GitHub, Pastebin, Telegram).
3.  **Active Reconnaissance** (`dark_web_probe`): Dynamically tasks the worker pipeline to initiate localized Tor-based keyword probes (e.g., via Ahmia).
4.  **Investigation Operations** (`create_task` / `flag_critical`): Automatically curates dedicated investigation plans, logging and tracking steps as collaborative task items.

The AI Engine combines these autonomous actions with direct PII identification, rendering immediate insights on validity and origin vector directly into the front-end dashboard.
