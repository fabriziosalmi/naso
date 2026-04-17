# Automation: SOAR Webhooks & CTI

NASO's pipeline can execute automated response actions when critical threats are detected.

## SOAR Webhooks

When a leak is processed with `severity_score >= 80`, NASO can fire a webhook to your SIEM/SOAR platform.

### Enabling the Hook

Set the following environment variable:

```bash
SOAR_WEBHOOK_URL="https://your-splunk-heavy-forwarder.corp.local/api/v1/stix-feed"
```

### Threshold

The SOAR trigger threshold is `80` (configurable at call time via the `ack-all` endpoint parameter).

### The Payload

NASO dispatches a non-blocking `POST` with a JSON body:

```json
{
  "alert_type": "CRITICAL_OSINT_LEAK",
  "details": {
    "tenant_id": "ORG-1X",
    "source": "tor-crawl",
    "severity_score": 98,
    "metadata_json": { ... }
  }
}
```

### Rate Limiting

The webhook call has a 3-second timeout and is fire-and-forget (non-blocking). Configure your SIEM to accept this payload format.

## CTI Adapters

NASO integrates with public, keyless CTI sources:

- **Bitcoin wallet balance** — queried from public blockchain explorers
- **IP threat scoring** — fetched from ThreatFox public API
- **YARA rule matching** — local rule engine against all ingested content

These integrations are implemented as Celery tasks and run asynchronously within the pipeline worker.
