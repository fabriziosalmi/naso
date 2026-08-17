---
layout: home

hero:
  name: "NASO"
  text: "Exposure monitoring you host yourself."
  tagline: "Ingest breach and dark-web material, correlate it into identities, and triage it with a local LLM. Every component runs in your own Compose stack — the data never leaves it."
  image:
    src: /logo.svg
    alt: NASO Logo
  actions:
    - theme: brand
      text: Documentation
      link: /guide/
    - theme: alt
      text: View API Reference
      link: /api/

features:
  - title: Model Context Protocol
    details: "An MCP server exposes six tools — dark-web, Shodan and Telegram recon, identity and leak lookups, and VIP protection — over the same tenant-scoped queries the API uses, and the tenant it is bound to is fixed in its environment, out of the model’s reach — so a client cannot reach another tenant. It is still a direct database connection: see the guide. Inference runs on your own hardware; payloads never leave it."
  - title: Streaming bulk ingestion
    details: "Large dumps are read line by line from a local file or a URL, never loaded whole. A regex pre-pass forwards only the matching chunks to the pipeline, on a worker pinned to concurrency 1 so one big job cannot starve the per-hit queue."
  - title: Identity correlation
    details: "Identities that appear in the same leak are proposed for merging with the shared leaks as evidence, and every merge is written to an append-only ledger that can be reversed. Leak text is deduplicated separately by SimHash with a Hamming-distance threshold."
  - title: Audit you can verify
    details: "Per-tenant scoping on every query, and an audit log chained by SHA-256 — each row carries the previous row's hash, so a deletion or an edit breaks the chain at a position the verify endpoint reports. It detects tampering; it does not prevent it."
  - title: Babel extractor
    details: "Regex extraction of emails, IPv4 addresses, and Bitcoin and Monero wallets, alongside a language-detection pass, over payloads in any script."
  - title: SOAR handoff
    details: "A JSON webhook fires on any hit scoring 90 or above, posted asynchronously so a slow SIEM never blocks the pipeline. The payload is NASO's own shape — it is not STIX."
---

<style>
/* Apple-Specific Local Overrides for Homepage Highlights */
.vp-doc h1 {
  letter-spacing: -0.02em;
}
</style>
