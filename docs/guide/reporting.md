# Reporting

Two report types: **per-leak evidence** PDFs and the **bulk dossier**. Both are signed when `NASO_PRIVATE_KEY_PATH` points at a valid private key. Plus a sibling: CSV export of the audit chain.

## Per-leak evidence PDF

`GET /leaks/{leak_id}/export` returns a PDF and a signature. Implementation: [`shared/utils/reporting.py::ForensicReportGenerator.generate_pdf`](https://github.com/fabriziosalmi/naso/blob/main/shared/utils/reporting.py).

Contents:

- Header with `Report ID = NASO-REP-<YYYYMMDD>-<leak_id[:8]>`, ISO timestamp, tenant name, source.
- **Evidence hash**: `SHA-256(leak_id + content)`. Lets the recipient verify the document body wasn't truncated/altered post-signing.
- **AI verdict** block from `metadata_json.ai_analysis.answer`.
- **Evidence snippet**: first 2 KB of the leak content (truncation marker if longer).
- Footer note about Tor-cluster provenance.

Response headers:

```
Content-Disposition: attachment; filename="NASO-EVIDENCE-<id8>.pdf"
X-Forensic-Signature: <hex>
```

`X-Forensic-Signature` is what changes depending on whether you have a key:

| `NASO_PRIVATE_KEY_PATH` | Signature                                                                                               |
|-------------------------|---------------------------------------------------------------------------------------------------------|
| **Set + valid PEM**     | RSA-PSS over SHA-256 (`MGF1(SHA256)`, `salt_length=MAX_LENGTH`) — court-grade                            |
| **Unset or fallback**   | `SHA-256(pdf_bytes)` hex — tamper-evidence hint, *not* a real signature                                  |

The fallback exists so a dev environment without a key still produces something; production must set the key.

### Key file permissions

`reporting.sign_report` refuses to load any private key whose mode allows group or world bits — i.e. anything outside `0o600` / `0o400`. The check raises `PermissionError` with an explicit message:

```
SECURITY: private key file '<path>' has unsafe permissions (mode 0o644).
Set permissions to 0o400 or 0o600 (owner read-only).
```

That's there because a leaked signing key destroys the forensic value of every dossier minted under it. See [Runbook → Forensic signing key compromise](runbook.md#forensic-signing-key-compromise).

### Verifying a signature

Receiver-side, given the public key (`naso_forensic_signing.pub.pem`):

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

with open("naso_forensic_signing.pub.pem", "rb") as f:
    pub = serialization.load_pem_public_key(f.read())

with open("NASO-EVIDENCE-<id8>.pdf", "rb") as f:
    pdf_bytes = f.read()

# X-Forensic-Signature header value, hex-decoded
signature = bytes.fromhex(SIGNATURE_HEX)

pub.verify(
    signature,
    pdf_bytes,
    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
    hashes.SHA256(),
)
# raises InvalidSignature if the PDF was tampered with after signing
```

## Bulk dossier export

`GET /leaks/export/dossier` aggregates every leak in the operator's tenant scope (or all tenants for admins) into one PDF:

- Cover page with tenant name + month/year.
- Executive summary (count, average severity).
- Per-incident block (1-2 leaks per page) with timestamp, severity, snippet.
- Same `X-Forensic-Signature` semantics as the per-leak PDF.

Filename: `NASO-FULL-DOSSIER.pdf`.

Returns `404` when there are no matching leaks (rather than emit an empty PDF).

## CSV export of the audit chain

`exportAuditCsv` in the SPA store ([`frontend/src/store/useNasoStore.js`](https://github.com/fabriziosalmi/naso/blob/main/frontend/src/store/useNasoStore.js)) takes the loaded audit log page and writes a CSV the analyst can hand to compliance. RFC 4180 quoting + leading-quote escape on cells starting with `=`/`+`/`-`/`@`/`\t`/`\r` (formula-injection mitigation per OWASP). The blob URL and `<a>` element are revoked / removed after the click — no leak.

Filename: `NASO-AUDIT-LOG.csv`.

## Audit log API

`GET /system/audit` returns a paginated view:

```http
GET /system/audit?limit=100&offset=0&action=IDENTITY_MERGED&resource_type=identity
```

Response shape:

```json
{
  "total": 4321,
  "limit": 100,
  "offset": 0,
  "items": [
    {
      "id": "...",
      "user_id": "...",
      "action": "IDENTITY_MERGED",
      "resource_type": "identity",
      "resource_id": "...",
      "timestamp": "2026-04-26T13:20:00+00:00",
      "details": { ... }
    }
  ]
}
```

Common actions emitted by the engine:

| Action                       | When                                                        |
|------------------------------|-------------------------------------------------------------|
| `LOGIN_SUCCESS` / `LOGIN_FAIL` | `/auth/login`                                              |
| `LOGOUT`                     | `/auth/logout`                                              |
| `INGEST_WEBHOOK`             | New webhook ingestion accepted                              |
| `CREATE_IDENTITY`            | Manual identity registration                                |
| `TOGGLE_PROTECTION`          | VIP flag changed                                            |
| `DARK_WEB_RECON`             | `/leaks/recon/darkweb`                                      |
| `SHODAN_RECON`               | `/leaks/recon/shodan`                                       |
| `TELEGRAM_RECON`             | `/leaks/recon/telegram`                                     |
| `IDENTITY_MERGED`            | A pair was merged                                           |
| `IDENTITY_MERGE_REVERSED`    | A merge was undone                                          |
| `UPDATE_LEAK_STATUS`         | `PATCH /leaks/{id}/status`                                  |
| `ACKNOWLEDGE_LEAK`           | Single ack                                                  |
| `ACKNOWLEDGE_ALL_CRITICAL`   | Bulk ack                                                    |
| `GENERATE_MASSIVE_DOSSIER`   | Dossier export                                              |
| `VIEW_LEAK_SCREENSHOT`       | Screenshot retrieval (forensic chain-of-custody)            |
| `UPDATE_PROFILE`             | Operator email change                                       |

Plus AI-driven variants when an action is performed by the Co-Analyst tool layer (audit row's `user_id` is still the operator who started the session).

## Audit chain integrity

`GET /system/audit/verify` walks the chain for the operator's tenant and returns `{ok, broken_at, reason, total}`. The SPA's integrity banner polls this every 5 minutes and turns red on `ok: false`. See [Security → Audit chain](security.md#audit-chain-tamper-evident) for the algorithm and [Runbook → Audit chain broken](runbook.md#audit-chain-broken) for response.

## Health monitoring

| Endpoint               | Purpose                                                                |
|------------------------|------------------------------------------------------------------------|
| `GET /system/status`   | Quick Postgres-only check (1× `SELECT 1` with latency)                 |
| `GET /system/health`   | Composite probe across PG / Redis / RabbitMQ / MinIO / Elasticsearch with 1s/probe cap. Auth-free so a load balancer can hit it. |

Wire `/system/health` to your orchestrator's liveness/readiness probe; keep `/system/status` for the SPA badge.
