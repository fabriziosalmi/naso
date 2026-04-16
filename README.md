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

### 2. NASO AI Co-Analyst
*   **Real-time AI Assistant**: Built-in reactive AI agent utilizing SSE (Server-Sent Events) for high-speed streaming interactions.
*   **Autonomous Tool Dispatch**: The AI dynamically invokes NASO backend tools (`search_identities`, `dark_web_probe`, `get_leaks`) based on context.
*   **Investigation Plans**: AI builds and tracks complex threat investigations, managing structured tasks in the database.
*   **Local LLM Integration**: Triage and chat executed via Local AI (e.g., LM Studio with `gemma-4-e2b-it`) eliminating external data leakage.

### 3. Identity Correlation
*   **Master Profile Unification**: Automated merging of fragmented identifiers (emails, usernames, hashes) into unified risk-scored profiles.
*   **Neural Topology**: Visualization of relationship matrices using force-directed graphs.

## Deployment

### Prerequisites
*   Docker 24.x+ and Docker Compose v2.x+
*   Local AI endpoint (LM Studio, Ollama, etc.) listening on port 1234.

### Execution
1.  Initialize environment:
    ```bash
    cp .env.example .env
    ```
    > **Note on AI Networking:** By default, NASO runs in Docker. To reach a local LM Studio instance running on your host machine, the `AI_ENDPOINT` in your `.env` must be explicitly set to `http://host.docker.internal:1234/v1`.

2.  Start the stack:
    ```bash
    docker-compose up -d --build
    ```
3.  Bootstrap the database to create system tenants, admin accounts, and required tables:
    ```bash
    docker exec naso-api python init_db.py
    ```

### Troubleshooting
*   **Database Tables Missing**: If you encounter errors relating to `investigation_plans` or similar tables not existing, ensure you have successfully executed `python init_db.py` inside the container.
*   **Vite Dev Server (Frontend)**: If modifying the frontend locally and you encounter a `__HMR_CONFIG_NAME__ is not defined` error, execute a hard refresh in your browser. If it persists, remove the `.vite` cache directory inside `frontend/node_modules/` or downgrade Vite to `6.2.7`.

## Documentation
Technical specifications and API references are available in the `/docs` directory, published via VitePress.

## Standards & Compliance
*   **Audit Logging**: Every operation is logged with ISO 8601 timestamps and resource-level attribution.
*   **Security**: No hardcoded credentials; strict environment variable enforcement.
