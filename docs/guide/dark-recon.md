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
| `POST /leaks/recon/telegram` | `POST` | Search Telegram via official Bot API (requires `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`) |

## Error Handling

When Tor nodes or external services become unreachable, the system raises an explicit error. The API returns an HTTP 503 with a descriptive message. Audit logs capture the failure event for post-incident review.
