# Dark Web Reconnaissance

NASO performs automated OSINT collection across the deep and dark web using stealth scraping heuristics and load-balanced Tor routing.

## Network Architecture

### Tor Cluster

NASO deploys a fleet of dedicated Tor containers (`naso-tor-1` through `naso-tor-5`) behind an **HAProxy load balancer** (`naso-tor-lb`). This architecture:

- Distributes requests across multiple Tor circuits, preventing IP-based blocking by hostile services
- Provides automatic failover if individual Tor nodes become unreachable
- Isolates Tor traffic within the internal Docker bridge network, ensuring no clearnet leakage

### Ahmia Integration

The primary search vector uses the Ahmia onion search engine. Queries are dispatched through the Tor cluster and results are parsed, deduplicated, and stored.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /leaks/recon/darkweb?q=<query>` | `GET` | Execute a dark web probe via Ahmia |
| `GET /leaks/recon/shodan?ip=<ip>` | `GET` | Query Shodan for a given IP address |
| `GET /leaks/recon/telegram?channel=<name>` | `GET` | Read a public channel's recent messages |

### How the Telegram probe works

It fetches `https://t.me/s/<channel>` — the public web preview Telegram serves to
anyone — and parses the message widgets out of the HTML. **No Bot API, no
credentials, and no `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`**: this page used to
claim all three. Those two variables belong to the separate Telethon listener in
`shared/tasks/telegram.py`, which is a different feature.

It follows that the probe only sees channels Telegram exposes publicly, and that
it goes out over the clearnet, not through Tor.

## Error Handling

A successful probe is written to the audit log (`DARK_WEB_RECON`) with the query and result count. If the Tor cluster or Ahmia is unreachable the probe raises, and the request surfaces as an error to the caller — it is not currently normalised to a 503, and a *failed* probe writes no audit entry (the audit write follows the search). Treat the audit log as a record of completed probes, not attempts.
