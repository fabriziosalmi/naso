# Goal: Fase 5 God-Tier - UX Suprema & Telemetria 🚀

L'applicazione è solida, ma un prodotto che sfida le grandi piattaforme ha bisogno di **Onboarding Infallibile**, **Monitoraggio in tempo reale** e **Micro-interazioni guidate**.
Questa è l'architettura per portare NASO al livello richiesto: far pregare gemini/claude.

## User Review Required

> [!CAUTION]
> Stiamo espandendo lo stack in modo massiccio per abbracciare vere operation enterprise. Verranno installati pacchetti React di alto livello (`sentry`, `joyride`, `cmdk`, `tooltip`) e il backend implementerà un middleware di bug-tracking globale.
> Conferma il perimetro d'azione delineato.

## Proposed Changes

---

### 1. Bug Tracking Universale (Sentry Integration)
Costruiremo una pipeline di Exception Handling trasparente. Il dev non dovrà più cercare gli errori, saranno loro a trovarlo.

#### [MODIFY] [backend/requirements.txt](file:///Users/fab/Documents/git/naso/backend/requirements.txt)
- Aggiunta di `sentry-sdk[fastapi]`. 
#### [MODIFY] [backend/app/main.py](file:///Users/fab/Documents/git/naso/backend/app/main.py)
- Inizializzazione Sentry DSN (via config).
- Creazione di un `GlobalExceptionHandler` unificato che assorbe i crash e li logga in async senza far cadere la response al frontend (500 gracefully degraded).
#### [MODIFY] [frontend/package.json](file:///Users/fab/Documents/git/naso/frontend/package.json)
- Aggiunta `@sentry/react` e `@sentry/tracing`.

---

### 2. Onboarding Infallibile & In-App Context (UX)
Un utente deve apprendere NASO nei primi 15 secondi senza leggere il manuale.

#### [NEW] [frontend/src/components/layout/OnboardingTour.jsx](file:///Users/fab/Documents/git/naso/frontend/src/components/layout/OnboardingTour.jsx)
- Integrare la libreria `react-joyride`. Verrà creata una sequenza guidata con highlight degli elementi DOM ("Questa è la Topology", "Da qui invochi il Co-Analyst", ecc.).
#### [MODIFY] [frontend/src/App.jsx](file:///Users/fab/Documents/git/naso/frontend/src/App.jsx)
- Iniezione dell'`OnboardingTour` visibile solo al primo login del token.
- Aggiunta di `@radix-ui/react-tooltip`. Verranno mappate tutte le icone del `Sidebar.jsx`, `Header.jsx` e `Dashboard.jsx`.

---

### 3. In-App Docs (CMDK - Command Palette)
Niente più spolete tra App e Markdown Documentation in nuove tab.

#### [NEW] [frontend/src/components/ui/CommandMenu.jsx](file:///Users/fab/Documents/git/naso/frontend/src/components/ui/CommandMenu.jsx)
- Tramite la celebre libreria `cmdk`, implementeremo la scorciatoia `CMD+K`.
- Un terminale flottante glassmorphism si aprirà, permettendo di navigare al volo verso le "AI Instructions", "Endpoint Specs" o eseguire azioni dirette.

---

### 4. Codebase Audit & Wiring (Backend Logic)
- **Check dei payload asincroni**: Assicurazione formale che i task Celery di ingestion non abbiano drop errors se Pydantic riceve fields sconosciuti in `Payload`. 
- **Graceful shutdown**: Il loop di RabbitMQ (`aio_pika`) e le connessioni asincrone verranno vincolate in un `asynccontextmanager` in `main.py` per non lasciare file descriptor aperti.

## Open Questions

- Attualmente non abbiamo un account `Sentry` reale. Vuoi che inizializzi il codice Sentry utilizzando un finto `SENTRY_DSN` in ambiente dev ignorando i log, o preferisci integrare una catch universale di log su file testuale? L'approccio Sentry Dummy è il più professionale.

## Verification Plan
1. Provocazione di un errore `500` intenzionale in una rotta API e verifica della catch di Sentry e del degrado UI (Error boundary frontend).
2. Apertura pulita del browser in E2E validation: il `Joyride` deve apparire al primo hit e la combo `CMD+k` deve far triggerare la palette in-app.
