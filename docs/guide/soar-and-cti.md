# Automation: SOAR Webhooks & CTI

NASO's pipeline can execute automated response actions when critical threats are detected.

## SOAR Webhooks

When a leak is processed with `severity_score >= 90`, NASO can fire a webhook to your SIEM/SOAR platform.

### Enabling the Hook

Set the following environment variable:

```bash
SOAR_WEBHOOK_URL="https://your-splunk-heavy-forwarder.corp.local/api/v1/naso-alerts"
```

### Threshold

`90`, and it is a constant in `shared/tasks/pipeline.py` — not configurable
without editing it.

::: warning This page used to say 80, "configurable via the `ack-all` endpoint parameter"
Both halves were wrong. `POST /leaks/ack-all` does take `min_severity`
(defaulting to 80), but it decides which already-stored leaks an operator marks
as acknowledged; it has nothing to do with the outbound webhook. Two different
thresholds, one of them documented in place of the other.
:::

### The Payload

NASO dispatches a non-blocking `POST` with a JSON body. **It is not STIX** —
the shape below is NASO's own, and a SIEM configured to expect STIX 2.1 will
reject it. (The variable in the source was called `stix_payload`, which is where
that claim came from and how it survived; it is called `soar_payload` now.)

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
