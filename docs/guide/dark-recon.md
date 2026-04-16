# Dark Web Reconnaissance

NASO utilizes stealth scraping heuristics and Tor routing networks to perform OSINT across the Deep Web.

## Mechanism

We initialize recursive scrapers using a **Load-Balanced HAProxy Array** of Tor containers (e.g., `naso-tor-1`, `naso-tor-2`), making attribution and IP blocking significantly harder for malicious services.

### Playwright Stealth
Naso instantiates a stealth-configured Chromium context through Playwright, applying random jitter and stripping common automation signatures, enabling the extraction of dynamic Onion service content that normal scrapers miss.

### Snapshot Evidence
When content is scanned, a localized screenshot is taken and sent immediately to MinIO for non-repudiable proof of the discovered leak.
