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

## AI Triage Implementation

NASO utilizes local Large Language Models (LLMs) to perform automated triage.

### Forensic Analysis Logic
The model evaluates artifacts based on:
*   **PII Density**: Count and sensitivity of Personally Identifiable Information.
*   **Credential Validity**: Verification of email:password patterns.
*   **Vector Classification**: Categorization into Financial, Source Code, or PII sectors.
