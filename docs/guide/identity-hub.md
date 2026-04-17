# Identity Hub

The NASO Identity Hub is the central correlation matrix for digital identities extracted from breach data, social networks, and dark-web telemetry.

## Core Capabilities

### Master Identity Merging

When overlapping indicators are detected across separate data sources (e.g., an email address appearing in a Telegram dump that also matches a username from a paste site), NASO clusters them under a unified **Master Identity** record.

The merge process:
- Runs as an OOM-safe batch operation within the Celery pipeline worker
- Uses deterministic hashing to prevent duplicate merges across concurrent executions
- Is triggered automatically when new leaks are ingested, or manually via the UI

### Risk Scoring

Each identity accumulates a composite risk score based on:
- **Breadth** — number of distinct breach sources
- **Depth** — severity scores of linked artifacts
- **Recency** — timestamp of the most recent compromise event

### VIP Protection

Critical identities can be flagged as `is_protected = true` via the UI toggle or the `PATCH /identities/{id}/protect` endpoint. Protected identities receive elevated monitoring and are visually distinguished in all views.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/identities/` | `GET` | List identities for the current tenant |
| `/identities/` | `POST` | Register a new monitored identity |
| `/identities/{id}` | `GET` | Get a single identity by ID |
| `/identities/{id}/insights` | `GET` | Deep forensic profile with breach timeline |
| `/identities/{id}/protect` | `PATCH` | Toggle VIP protection status |
| `/identities/graph` | `GET` | Force-graph topology data for the tenant |

## Audit Logging

Every identity action is recorded in the `audit_logs` table with user ID, timestamp, and structured details.
