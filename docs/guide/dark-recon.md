# Dark Web Reconnaissance

NASO performs automated OSINT collection across the deep and dark web using stealth scraping heuristics and load-balanced Tor routing.

## Network Architecture

### Tor Cluster

NASO deploys a fleet of dedicated Tor containers (`naso-tor-1` through `naso-tor-5`) behind an **HAProxy load balancer** (`naso-tor-lb`). This architecture:

- Distributes requests across multiple Tor circuits, preventing IP-based blocking by hostile services.
- Provides automatic failover if individual Tor nodes become unreachable.
- Isolates Tor traffic within the internal Docker network, ensuring no clearnet leakage.

### Playwright Stealth

For dynamic content extraction, NASO instantiates a stealth-configured Chromium context via Playwright. The browser automation layer:

- Applies randomized viewport sizes, user-agent strings, and input timing jitter.
- Strips common automation signatures (`navigator.webdriver`, Chrome DevTools Protocol markers).
- Enables extraction of JavaScript-rendered onion service content that standard HTTP scrapers miss.

## Search Interface

### Ahmia Integration

The primary search vector uses the Ahmia onion search engine. Queries are dispatched through the Tor cluster and results are parsed, deduplicated, and stored.

### Fail-Fast Error Reporting

When Tor nodes or the Ahmia endpoint become unreachable, the system raises an explicit `ValueError` rather than silently returning empty results. This ensures:

- The UI displays a clear "Node Offline" status to the analyst.
- No false negatives contaminate the investigation record.
- Audit logs capture the failure event for post-incident review.

## Forensic Evidence Capture

When content matching monitored keywords is discovered:

1. A full-page screenshot is captured by the Playwright instance.
2. The screenshot is uploaded to MinIO object storage with a unique artifact key.
3. The leak record in PostgreSQL is linked to the screenshot via the `screenshot_path` field.
4. The original content snippet is indexed in Elasticsearch for sub-millisecond retrieval.

This non-repudiable evidence chain ensures that discovered leaks can be verified even if the original onion service goes offline.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /leaks/recon/darkweb?q=<query>` | `GET` | Execute a dark web probe via Ahmia |
