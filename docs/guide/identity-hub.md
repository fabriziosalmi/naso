# Identity Hub

The NASO Identity Hub operates as the central correlation matrix for digital identities extracted from breach data, social networks, and dark-web telemetry.

## Core Capabilities

### Master Identity Merging
When overlapping indicators are detected across separate data sources (e.g., an email address appearing in a Telegram dump that also matches a username from a paste site), NASO automatically clusters them under a unified **Master Identity** record. This merging process:

- Runs as an OOM-safe batch operation, processing up to 5,000 identity nodes per cycle.
- Uses deterministic hashing to prevent duplicate merges across concurrent worker executions.
- Can be triggered manually via the UI ("Auto-Merge" button) or programmatically through `POST /identities/merge`.

### Visual Investigation Navigation
Force-directed network graphs render identity clusters in real time, highlighting the intersections between:

- **Victims** (identity nodes)
- **Tactics** (MITRE ATT&CK technique associations)
- **Breach artifacts** (leak records linked to each identity)

Admin-role users bypass tenant isolation to visualize the full cross-tenant neural topology.

### Automated Risk Scoring
Each identity accumulates a composite risk score based on:

- **Breadth** of associated leaks (number of distinct breach sources)
- **Depth** of exposure (severity scores of linked artifacts)
- **Recency** of the most recent compromise event

### VIP Protection
Critical identities can be flagged as `is_protected = true`, either manually through the UI or via the AI Co-Analyst's `toggle_identity_vip` tool. Protected identities receive elevated monitoring priority and are visually distinguished across all views.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/identities/` | `GET` | List all identities for the current tenant |
| `/identities/` | `POST` | Register a new monitored identity |
| `/identities/{id}/insights` | `GET` | Deep forensic profile with breach timeline |
| `/identities/{id}/protect` | `PATCH` | Toggle VIP protection status |
| `/identities/merge` | `POST` | Trigger batch auto-merge across all identities |
| `/identities/graph` | `GET` | Retrieve force-graph topology data |
