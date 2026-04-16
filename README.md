# NASO Forensic Engine

NASO is a high-performance intelligence framework for real-time data breach monitoring, identity correlation, and forensic artifact ingestion. It implements an asynchronous core designed for high-concurrency environments and multi-tenant isolation.

## Technical Architecture

### Core Components
*   **Asynchronous API**: Built with FastAPI and SQLAlchemy 2.0 (Asyncpg driver). Implements OAuth2 with PBKDF2-SHA256 password hashing.
*   **Intelligence Pipeline**: Distributed task processing via Celery and RabbitMQ. 
*   **Persistence Layer**: PostgreSQL for relational data, Elasticsearch 8.x for full-text artifact indexing, and MinIO for forensic image storage.
*   **Anonymization Layer**: HAProxy-managed Tor rotating exit nodes for resilient Dark Web crawling.

### Resilience Patterns
*   **Saga Pattern**: Orchestrates distributed transactions for tenant data decommissioning across PostgreSQL, Elasticsearch, and MinIO.
*   **Circuit Breakers**: Protects external service calls (MinIO, Elasticsearch) from cascading failures.
*   **Bulkheading**: Isolated worker pools for heterogeneous ingestion sources (Telegram, Tor, GitHub).

## Features

### 1. Multi-Vector Ingestion
*   **Real-time Telegram Monitoring**: Event-driven listener using Telethon for immediate artifact ingestion.
*   **Recursive Tor Crawling**: Deep-portal exploration using Playwright Stealth and rotating proxies.
*   **GitHub/Pastebin Scraping**: Pattern-based scanning for secrets and credentials.

### 2. AI-Driven Triage
*   **Local LLM Integration**: Triage executed via Gemma-4-E2B-it (local endpoint).
*   **Forensic Prompting**: Structured analysis of intent, probability, and artifact classification.

### 3. Identity Correlation
*   **Master Profile Unification**: Automated merging of fragmented identifiers (emails, usernames, hashes) into unified risk-scored profiles.
*   **Neural Topology**: Visualization of relationship matrices using force-directed graphs.

## Deployment

### Prerequisites
*   Docker 24.x+ and Docker Compose v2.x+
*   Local AI endpoint (LM Studio or similar) listening on port 1234.

### Execution
1.  Initialize environment:
    ```bash
    cp .env.example .env
    ```
2.  Start the stack:
    ```bash
    docker-compose up -d --build
    ```
3.  Bootstrap the database:
    ```bash
    docker exec naso-api python init_db.py
    ```

## Documentation
Technical specifications and API references are available in the `/docs` directory, published via VitePress.

## Standards & Compliance
*   **Audit Logging**: Every operation is logged with ISO 8601 timestamps and resource-level attribution.
*   **Security**: No hardcoded credentials; strict environment variable enforcement.
