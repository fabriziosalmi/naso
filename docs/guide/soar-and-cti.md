# Automation: SOAR Webhooks & Keyless CTI

NASO is designed to operate autonomously in enterprise environments. Its pipeline executes two highly critical phases automatically before forensic data ever hits the disk: **Language Inference (Babel)** and **Automated Response (SOAR)**.

## The Babel Node (NLP Filter)
Before processing raw web leaks, the NASO engine feeds the content into the `BabelNode`.
1. **Heuristics Mapping**: Scans the payload for Unicode block clusters matching Cyrillic (Russian), Hanzi (Chinese), Arabic, and other target tracking languages.
2. **Textual NERExtraction**: Parses raw lines to detect and store underlying indicators like standard standard IPs, E-mails, and advanced indicators like **Bitcoin and Monero wallets**.

## Keyless CTI Adapters
NASO operates securely *without* requiring the purchase of paid Tier 1 CTI feeds.
Whenever Babel detects a Bitcoin Wallet, a Celery hook fetches the latest balance and transaction history from public explorers (e.g. `blockchain.info`) completely anonymously. IP addresses are automatically bounced off the ThreatFox API for public malware correlation scoring.

## SOAR (Security Orchestration, Automation, and Response) Webhooks
If the YARA engine or the local LLM scores a leak with a `severity_score >= 90`, waiting for human intervention is unviable.

### Enabling the Hook
Set the following environment variable in `.env`:
```bash
SOAR_WEBHOOK_URL="https://splunk-heavy-forwarder.corp.local/api/v1/stix-feed"
```

### The Payload
NASO will immediately dispatch a non-blocking `POST` request formulated as a quasi-STIX JSON payload:
```json
{
  "alert_type": "CRITICAL_OSINT_LEAK",
  "details": {
    "tenant_id": "ORG-1X",
    "source": "tor-crawl",
    "severity_score": 98,
    "metadata_json": {
       "babel": { ... }
    }
  }
}
```
This payload can be intercepted by firewalls to instantly burn/ban IP ranges or used by Azure AD APIs to force credentials rotations on compromised employees.
