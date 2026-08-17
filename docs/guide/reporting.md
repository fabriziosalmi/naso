# Compliance Data & Reporting

NASO provides structured reporting pipelines designed for compliance officers, legal teams, and incident response coordinators.

## Massive Dossier Export

Analysts can retrieve a PDF dossier of the tenant's leak records, signed with the
deployment's RSA key so a recipient can verify it was not altered after export.
Whether that satisfies any particular court is a question for a lawyer, not for
this page. The export pipeline:

- Aggregates all leak records matching the current tenant's scope.
- Attaches forensic metadata including SHA256 artifact hashes, discovery timestamps, and source vectors.
- Returns a downloadable binary blob via `GET /leaks/export/dossier`.

If no matching records exist, the endpoint returns a `404` response to prevent empty document generation.

## Audit Trail

Actions are written to `audit_logs`, readable at `GET /system/audit` (paged,
`?limit=` up to 200 and `?offset=`).

The ledger is **tamper-evident, not immutable**: each row carries a SHA-256 over
its own content and the previous row's hash, so an edit or a deletion breaks the
chain and `GET /system/audit/verify` reports the position it broke at. Anyone
with write access to the database can still change a row — they simply cannot do
it without the verifier noticing. Do not describe it to an auditor as immutable.

### Tracked Events

The action strings as they appear in the table:

| Action | Trigger |
|---|---|
| `CREATE_IDENTITY` | New identity registered |
| `VIEW_IDENTITY_INSIGHTS` | Identity dossier opened |
| `RUN_AUTO_MERGE` / `EXECUTE_MERGES` / `REVERSE_MERGE` | Merge proposed, applied, undone |
| `DARK_WEB_RECON` / `SHODAN_RECON` / `TELEGRAM_RECON` | Probe executed |
| `UPDATE_LEAK_STATUS` / `ACKNOWLEDGE_LEAK` / `ACKNOWLEDGE_ALL_CRITICAL` | Triage |
| `GENERATE_MASSIVE_DOSSIER` / `VIEW_LEAK_SCREENSHOT` | Evidence exported or viewed |
| `CREATE_TENANT` / `DELETE_TENANT_TRIGGERED` / `UPDATE_PROFILE` | Administration |
| `CREATE_YARA_RULE` / `DELETE_YARA_RULE` | Rule changes |
| `AI_CHAT` / `AI_DARK_WEB_PROBE` / `AI_FLAG_LEAK` / `AI_TOGGLE_VIP` | Co-Analyst actions |
| `MCP_TOOL_UPDATE_PROTECTION` | VIP flag changed through the MCP server |

::: warning Authentication is not audited
There is no `LOGIN` event — this page listed one, and `auth.py` writes no audit
entry at all. Successful and failed sign-ins are not in the ledger, and neither
is the toggle behind `PATCH /identities/{id}/protect` when it comes from the UI
rather than from the AI or MCP paths. If your compliance regime needs
authentication events, they have to be added before you rely on this table.
:::
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
