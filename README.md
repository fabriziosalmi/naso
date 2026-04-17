<div align="center">
  <img src="https://raw.githubusercontent.com/fabriziosalmi/naso/main/docs/public/logo.svg" width="120" alt="NASO Logo" />
  <h1>NASO Forensic Engine</h1>
  <p>
    <strong>Mission-Critical Cyber Threat Intelligence & OSINT Automation Platform</strong><br/>
    <em>High-performance data breach monitoring, AI correlation, and sovereign data lakes.</em>
  </p>

  <p>
    <a href="https://github.com/fabriziosalmi/naso/actions"><img src="https://img.shields.io/github/actions/workflow/status/fabriziosalmi/naso/build.yml?style=flat-square" alt="Build Status"></a>
    <a href="https://github.com/fabriziosalmi/naso/network/members"><img src="https://img.shields.io/github/forks/fabriziosalmi/naso?style=flat-square" alt="Forks"></a>
    <a href="https://github.com/fabriziosalmi/naso/blob/main/LICENSE"><img src="https://img.shields.io/github/license/fabriziosalmi/naso?style=flat-square" alt="License"></a>
  </p>
</div>

---

NASO is a **Data-Sovereign, High-Performance Intelligence Engine** designed exclusively for enterprise SecOps and Red Teams. It integrates asynchronous processing, strict Zero-Trust paradigms, and Local AI (via Model Context Protocol) to seamlessly analyze massive dark-web data leaks without exposing internal PII to external cloud inference vendors.

## 1. System Architecture

NASO leverages a partitioned, horizontally scalable backend via RabbitMQ and Celery Workers, strictly separated by task computational weight.

```mermaid
graph TD
    %% Define Styles
    classDef intel fill:#1A1A1A,stroke:#3B82F6,stroke-width:2px,color:#FFFFFF;
    classDef worker fill:#312E81,stroke:#6366F1,stroke-width:2px,color:#FFFFFF;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#FFFFFF;
    classDef external fill:#7F1D1D,stroke:#EF4444,stroke-width:2px,color:#FFFFFF;
    
    A1((Custom Scrapers)):::external
    A2((Dark Web JSON)):::external
    
    B(POST /leaks/ingest/webhook):::intel
    A1 & A2 -->|Raw Data| B
    
    B --> C[RabbitMQ Broker]:::worker
    C --> D[Celery Pipeline]:::worker
    
    D --> E{Local LLM / YARA Engine}:::intel
    
    E -->|Indicators| F1(PostgreSQL):::storage
    E -->|Full-Text Index| F2(Elasticsearch):::storage
    E -->|Binary Artifacts| F3(MinIO Object Store):::storage
```

## 2. Platform Capabilities (1:1 Codebase Mapping)

### 2.1 Universal Threat Ingestion (BYO-Data)
NASO operates on a "Bring Your Own Data" model. The system exposes a constant, non-blocking webhook (`POST /leaks/ingest/webhook`) that accepts raw, unformatted JSON from any arbitrary external script. The FastAPI layer immediately redirects the payload to the Celery asynchronous pipeline for backend LLM evaluation and YARA rule execution, guaranteeing zero HTTP-thread blockage.

### 2.2 Local AI Co-Analyst & Correlation
Integration with local LLM runtimes (LM Studio, Ollama) operates natively over REST (`/ai/chat`) utilizing Server-Sent Events (SSE). The AI acts natively via defined Tool Calls (`search_identities`, `get_leaks`, `dark_web_probe`) to autonomously evaluate local PostgreSQL telemetry without data exfiltration. 

### 2.3 Force-Directed Topology Graph
The React-based frontend aggregates complex primary keys from the `identity_leaks` SQL table into an interactive 2D Canvas matrix. Nodes utilize dynamic scaling based on graph degree-centrality, ensuring visual isolation of critical compromised assets globally.

## 3. Provisioning & Deployment

NASO infrastructure relies strictly on `.env` bindings and automated Docker provisioning. 

### Step 1: Initialize the Environment
```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso
cp .env.example .env
# Edit .env and supply rigid PostgreSQL/RabbitMQ passwords
```

### Step 2: Deploy the Sovereign Data Engine
```bash
make up
```

### Step 3: Zero-to-Hero Initialization (Demo Mode)
To immediately populate the system graph with complex, synthetic threat telemetry (VIP accounts, Dark Web breaches, and Mitre mappings) without establishing a live production feed, execute the demo seeder core:
```bash
make demo
```
*Users can verify the live execution at `http://localhost:5173` with credentials `admin@naso.local` / `admin`.*

## 4. Continuous Integration & Draconian Testing

NASO ships with an integrated, multi-layered regression enforcement suite (`cli/validate.sh`). This script executes before commits to guarantee absolute architectural integrity:

1. **Pytest Backend Verification**: Asserts multi-tenant JWT boundaries, simulates disconnected Celery fallback states, and validates the AI tool dispatcher.
2. **Vitest State Machine**: Triggers mock executions against the React/Zustand logic (simulating `HTTP 401 Unauthorized` flushes).
3. **Playwright UI E2E**: Dispatches an embedded headless browser mapping the human forensic flow (Login -> Topology Visualizer -> OSINT Query -> System Logout).

To execute the test matrix:
```bash
./cli/validate.sh
```

## 5. Technical Documentation
Explore the full developer and agent orchestration specs in the `docs/` VitePress suite:

* [MCP Server Integration](https://fabriziosalmi.github.io/naso/guide/mcp-integration)
* [SOAR Architectures & CTI Setup](https://fabriziosalmi.github.io/naso/guide/soar-and-cti)

To compile the documentation locally:
```bash
cd docs && npm ci && npm run docs:dev
```

---
*Developed under MIT License pattern. Mission-critical deployment usage relies on the security posture of the host hypervisor.*
