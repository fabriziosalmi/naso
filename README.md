# NASO ELITE - Advanced Forensic & Intelligence Framework

NASO is a mission-critical, high-performance forensic framework designed for real-time threat intelligence, leak detection, and automated target reconnaissance.

## 🚀 Key Features

- **Multi-Source Ingestion**: Automated scraping from Dark Web (.onion), Telegram, GitHub, and Pastebin.
- **AI-Powered Triage**: Deep content analysis using Gemma 4 with structured "thinking" logs.
- **Identity Merging & Recon**: Advanced algorithms to correlate fragmented identities into unified master profiles.
- **Network Topology Pro**: Interactive force-directed graphs for visualizing compromise paths.
- **Forensic Evidence**: Full-page screenshots of Dark Web leaks saved securely on MinIO.
- **Enterprise Reporting**: Massive PDF dossier generation with cryptographic digital signatures.
- **Audit & Compliance**: Full SOC2/ISO27001 compliant logging of all analyst actions.
- **Resilient Infrastructure**: Built-in Circuit Breakers, Bulkheads, and Distributed Tracing (OpenTelemetry).

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.14+), SQLAlchemy (Async), PostgreSQL, Celery, Redis.
- **Intelligence**: YARA, Gemma 4 (Local AI), Ahmia API.
- **Infrastructure**: Elasticsearch, MinIO, Tor Rotating Cluster, RabbitMQ, Jaeger.
- **Frontend**: React 18, Vite, Tailwind CSS, shadcn/ui, Recharts, react-force-graph.

## 📦 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.14+
- Node.js 20+

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/fabriziosalmi/naso.git
   cd naso
   ```

2. **Environment Setup**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Launch Infrastructure**:
   ```bash
   docker-compose up -d
   ```

4. **Initialize Database**:
   ```bash
   docker-compose exec backend python init_db.py
   ```

5. **Start Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm run test        # Unit tests
npm run test:e2e    # E2E tests (requires dev server)
```

## 📖 Documentation

Full documentation is available in the `/docs` directory and can be viewed via VitePress.

## ⚖️ License

Proprietary Forensic Software - All Rights Reserved.
