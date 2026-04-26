---
layout: home

hero:
  name: NASO
  text: Forensic Engine
  tagline: Self-hosted breach monitoring, identity correlation, and a local-AI co-analyst. Runs on your hardware; the data never leaves the network.
  actions:
    - theme: brand
      text: Get started
      link: /guide/
    - theme: alt
      text: API reference
      link: /api/
    - theme: alt
      text: GitHub
      link: https://github.com/fabriziosalmi/naso

features:
  - title: FastAPI + async core
    details: |
      Single async stack. SQLAlchemy 2 + asyncpg, slowapi rate-limiting,
      orjson, aio_pika webhooks. No thread pool fallback in the hot path.
    link: /guide/architecture
    linkText: Architecture

  - title: JWT EdDSA, JTI revocable
    details: |
      Ed25519 access tokens with iss / aud / nbf / exp / jti. Logout adds
      the JTI to a Redis blacklist with TTL equal to the remaining
      lifetime. Algorithm whitelist of one — alg-confusion blocked.
    link: /guide/security#authentication
    linkText: Security

  - title: CSRF double-submit
    details: |
      httpOnly auth cookie + non-httpOnly naso_csrf cookie verified with
      secrets.compare_digest. Bearer / server-to-server callers exempted
      automatically. Test matrix in tests/test_csrf.py.
    link: /guide/security#cookie-csrf
    linkText: Security model

  - title: Hash-chained audit log
    details: |
      Per-tenant SHA-256 chain over canonical JSON. Postgres
      pg_advisory_xact_lock + asyncio.Lock for concurrent appends.
      Verification via /system/audit/verify; UI banner polls every 5 min.
    link: /guide/security#audit-chain-tamper-evident
    linkText: How it works

  - title: Identity correlation
    details: |
      Normalization (Gmail dot/plus, phone digits), 64-bit SimHash
      near-duplicate detection at Hamming ≤ 3, evidence-based merging
      with explicit invariants (CrossTenantMerge, VipInvariantViolation).
    link: /guide/identity-hub
    linkText: Identity Hub

  - title: Tor + Ahmia client
    details: |
      Five Tor instances behind HAProxy. Token-bucket rate limit, circuit
      breaker, retry with full-jitter backoff, optional NEWNYM rotation
      per query. Result cache with bounded size + TTL.
    link: /guide/dark-recon
    linkText: Dark recon

  - title: Local LLM co-analyst
    details: |
      OpenAI-compatible endpoint (LM Studio, Ollama, vLLM). Multi-round
      ReAct loop with tool calling, parallel execution via asyncio.gather
      with a fresh AsyncSession per tool. Bounded iterations.
    link: /guide/ai-coanalyst
    linkText: AI Co-Analyst

  - title: HMAC-signed SOAR webhook
    details: |
      Critical alerts (severity_score ≥ 90) POST X-Naso-Timestamp +
      X-Naso-Signature-256 over <ts>.<body>. Receivers reject deliveries
      older than 5 minutes and compare_digest the MAC.
    link: /guide/soar-and-cti
    linkText: SOAR & CTI

  - title: Composite health probe
    details: |
      /system/health pings PostgreSQL, Redis, RabbitMQ, MinIO,
      Elasticsearch in parallel under a 1 s cap. Reports
      ok | degraded | down. Auth-free for the load balancer.
    link: /guide/runbook#system-health-composite-probe
    linkText: Runbook
---

<style scoped>
/* Tighten the home a little — VitePress's default heros leans long. */
.VPHome .VPHero .name {
  font-size: clamp(40px, 6vw, 72px);
}
.VPHome .VPHero .text {
  font-size: clamp(28px, 4vw, 48px);
  margin-top: 4px;
}
.VPHome .VPHero .tagline {
  margin-top: 24px;
  font-size: 18px;
  max-width: 640px;
}
.VPHome .VPFeatures .container {
  max-width: 1200px;
}
</style>
