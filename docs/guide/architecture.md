# Deep Architecture

NASO utilizes a heavily decoupled microservices design to achieve maximum throughput for forensic evidence parsing.

## 1. Web Layer
- Built with **FastAPI**.
- Communicates transparently with `SQLAlchemy 2.0 (asyncpg)`.
- Enforces multi-tenancy rules and JSON web tokens (JWT).

## 2. Ingestion & Analysis Pipelines (Workers)
- Operates via **Celery**, backed by **RabbitMQ**.
- Workers run isolated in restrictive docker containers without root privileges (`no-new-privileges` enabled, `cap_drop` ALL enforced).
- They perform scraping logic (Telegram, Tor) and hash artifacts through an algorithmic deduplication engine.

## 3. Storage Hierarchy
- **Postgres (Metadata)**: Stores models, users, tenants, rules, and investigation plans.
- **MinIO (Binary blobs)**: Images, forensic web-snapshots, JSON payloads.
- **Elasticsearch (Search Vectors)**: Real-time Kibana/Lucene compliant search matrices.
