---
layout: home

hero:
  name: "NASO"
  text: "The Forensic Intelligence Standard."
  tagline: "Unify external intelligence, dark web reconnaissance, and AI-driven identity correlation in a single, high-performance platform."
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
    details: "Native MCP support binds an MCP-capable client directly to the PostgreSQL intelligence lake. Inference can run entirely on your own hardware, so payloads never leave your infrastructure."
  - title: Massive Data Scalability
    details: "Async Celery worker partitioning with OOM-safe streaming. Large dumps are read line by line from a local file or URL, and only the chunks that match are forwarded to the pipeline."
  - title: Identity Correlation
    details: "SimHash fingerprints and Hamming-distance clustering merge threat actor aliases, email patterns, and Tor domains, with every merge recorded in a reversible audit event."
  - title: Zero-Trust Telemetry
    details: "Per-tenant isolation, a hash-chained audit log whose integrity can be verified on demand, and local database latency checks."
  - title: Babel NLP Extractor
    details: Intelligent pattern matching extracts IOCs, Cryptowallets, and keys across multilingual deep web payloads.
  - title: SOAR Integration
    details: Fail-fast outbound webhooks to dispatch structured JSON STIX profiles to any enterprise SIEM instance.
---

<style>
/* Apple-Specific Local Overrides for Homepage Highlights */
.vp-doc h1 {
  letter-spacing: -0.02em;
}
</style>
