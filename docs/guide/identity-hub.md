# Identity Hub

The Identity Hub is where the identifiers pulled out of breach material — email addresses, usernames, wallet addresses — are correlated into people.

## Core Capabilities

### Master Identity Merging

When overlapping indicators are detected across separate data sources (e.g., an email address appearing in a Telegram dump that also matches a username from a paste site), NASO clusters them under a unified **Master Identity** record.

The merge process:
- Proposes a pair when two identities appear in the same leak, and carries the
  shared leak ids as the evidence for that proposal
- Writes every merge to an append-only ledger (`merge_events`), chained and
  reversible — `POST /identities/merges/{id}/reverse` undoes one and records
  the reason
- Runs in the Celery pipeline worker on ingest, or on demand from the UI

### Risk Scoring

Each identity accumulates a composite risk score based on:
- **Breadth** — number of distinct breach sources
- **Depth** — severity scores of linked artifacts
- **Recency** — timestamp of the most recent compromise event

### VIP Protection

Critical identities can be flagged as `is_protected = true` via the UI toggle or the `PATCH /identities/{id}/protect` endpoint, and are visually distinguished in all views.

Concretely, the flag changes one thing in the pipeline: a hit involving a
protected identity raises a priority notification and fires the outbound webhook
**below** the normal critical threshold, tagged `[VIP]`. A leak that would
otherwise pass unremarked does not pass unremarked for these.

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
