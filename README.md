<div align="center">
  <img src="https://raw.githubusercontent.com/fabriziosalmi/naso/main/docs/public/logo.png" width="120" alt="NASO Logo" />
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

NASO is a **Data-Sovereign, High-Performance Intelligence Engine** designed exclusively for enterprise SecOps and Red Teams. It integrates async processing, strict Zero-Trust paradigms, and Local AI (Model Context Protocol) to seamlessly analyze massive dark-web data leaks without exposing PII to external vendors.

## Core Architecture
NASO leverages a partitioned, horizontally scalable backend via Celery Workers separated by task weight (Recon vs Streaming).

```mermaid
graph TD
    %% Define Styles
    classDef intel fill:#1A1A1A,stroke:#3B82F6,stroke-width:2px,color:#FFFFFF;
    classDef worker fill:#312E81,stroke:#6366F1,stroke-width:2px,color:#FFFFFF;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#FFFFFF;
    classDef external fill:#7F1D1D,stroke:#EF4444,stroke-width:2px,color:#FFFFFF;
    
    A1((Dark Web)):::external
    A2((Paste Sites)):::external
    A3((Combo Lists)):::external

    B(NASO Async API):::intel
    A1 & A2 & A3 -->|Triggers| B
    
    B -->|Fast Route| C[Worker: Pipeline]:::worker
    B -->|Massive Streaming| D[Worker: Massive]:::worker
    
    C --> E{Babel NLP Node}:::intel
    D -->|Lines / Regex| E
    
    E -->|Indicators| F1(PostgreSQL):::storage
    E -->|Full-Text| F2(Elasticsearch):::storage
    E -->|Blobs/Images| F3(MinIO Space):::storage
    
    E -->|Severity > 90| G((SOAR SIEM Webhook)):::external
    
    H[MCP Local Agent]:::intel -->|Direct Access| B
```

## Flagship Features

| Capability | Description |
|---|---|
| **Massive Leak Streaming** | OOM-safe chunk streaming for gigabyte-scale TXT/CSV combos. No RAM saturation even with 100GB files. |
| **Model Context Protocol (MCP)** | Plug your Claude Desktop directly into NASO via a zero-cost local interface for autonomous DB investigation. |
| **The "Babel" Node** | Unicode detection for Russian/Chinese threat forums, triggering local LangChain translation and Entity extraction. |
| **Keyless CTI Adapters** | Automatic, stealthy enrichment via public `blockchain.info` and ThreatFox endpoints *without* paid API keys. |
| **OPSEC Fingerprinting** | Defensive crawling with headless Playwright. Spoofer engine bypasses DDoS-Guard and WAFs with generative canvases. |
| **Fail-Fast Security** | Brutal zero-fallback configuration. No hardcoded credentials to ensure compliance with military deployment schemas. |

## Quick Deployment

NASO relies strictly on `.env` bindings. Before launching, adapt `docker-compose.yml` specs or just run the fast local environment.

```bash
# 1. Prepare Sovereign Environment
cp .env.example .env
# Edit .env and supply rigid PostgreSQL/RabbitMQ passwords

# 2. Deploy the Data Lake
docker-compose up -d --build

# 3. Bootstrap Tables & Identity Maps
docker exec naso-api python init_db.py
```

## Glassmorphism UI
Run the ultra-responsive, GPU-accelerated frontend crafted for CTI analysts.
Navigate to `http://localhost:5173`. Contains real-time Neural Topology Maps, Dark Recon Dashboards, and full SSE streaming for the Co-Analyst.

> **Local AI Note**: If linking an internal AI model like Ollama or LM Studio, verify your `.env` lists `AI_ENDPOINT=http://host.docker.internal:1234/v1` for Docker internal routing.

## Technical Documentation
Explore the full developer and agent orchestration specs in the `docs/` VitePress suite:
* [MCP Server Integration](/docs/guide/mcp-integration)
* [SOAR Architectures & CTI Setup](/docs/guide/soar-and-cti)

To run the docs locally:
```bash
cd docs && npm ci && npm run docs:dev
```

---
*Developed under MIT License pattern. Use responsibly.*
