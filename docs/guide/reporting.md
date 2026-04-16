# Compliance Data & Reporting

NASO provides structured reporting pipelines designed for compliance officers, legal teams, and incident response coordinators.

## Massive Dossier Export

Analysts can retrieve exhaustive PDF dossiers that bind raw JSON metadata into court-ready documentation formats. The export pipeline:

- Aggregates all leak records matching the current tenant's scope.
- Attaches forensic metadata including SHA256 artifact hashes, discovery timestamps, and source vectors.
- Returns a downloadable binary blob via `GET /leaks/export/dossier`.

If no matching records exist, the endpoint returns a `404` response to prevent empty document generation.

## Audit Trail

NASO logs every user-driven and AI-driven action into a central, immutable audit ledger accessible at `GET /system/audit`.

### Tracked Events

| Action | Trigger |
|---|---|
| `LOGIN` | User authentication |
| `CREATE_IDENTITY` | New identity registered |
| `TOGGLE_PROTECTION` | VIP status changed |
| `DARK_WEB_SEARCH` | Onion probe executed |
| `AI_CHAT` | Co-Analyst session initiated |
| `AI_DARK_WEB_PROBE` | AI-triggered dark web search |
| `AI_FLAG_LEAK` | AI changed leak triage status |
| `AI_TOGGLE_VIP` | AI modified identity protection |
| `CREATE_INVESTIGATION` | New investigation plan created |

### CSV Export

The audit log supports client-side CSV export for offline analysis and compliance archival. The export generates RFC 4180-compliant CSV with proper quoting for JSON detail fields.

## System Health Monitoring

The `/system/status` endpoint performs a live database latency check by executing a `SELECT 1` query and timing the round-trip. This provides authentic operational telemetry rather than static mock values.

```json
{
  "status": "operational",
  "latency_ms": {
    "total": 2.34
  }
}
```
