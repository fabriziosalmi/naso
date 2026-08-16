# Security Policy

NASO processes breach data, dark web telemetry, and other sensitive material.
A vulnerability here can expose the data an operator is trying to protect, so we
take reports seriously and ask that you report them privately.

## Supported versions

NASO is pre-1.0 and is developed on `main`. Only the latest commit on `main`
receives security fixes. There are no backports to older tags.

| Version | Supported |
|---------|-----------|
| `main`  | ✅        |
| older tags | ❌     |

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it through one of these channels:

1. **Preferred** — [GitHub private security advisory](https://github.com/fabriziosalmi/naso/security/advisories/new).
   This keeps the report private until a fix ships and gives you credit on the
   published advisory.
2. **Email** — <fabrizio.salmi@gmail.com>, with `NASO SECURITY` in the subject.

Please include, as far as you can:

- the affected component (API endpoint, Celery task, worker, frontend route);
- the version or commit SHA you tested;
- a minimal reproduction — request, payload, or steps;
- the impact you believe it has;
- any proposed fix.

## What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement of your report | 5 business days |
| Initial assessment and severity | 10 business days |
| Fix or documented mitigation for high/critical | 30 days |

This is a single-maintainer project, not a funded security team. These are
good-faith targets, not a contractual SLA. If a deadline slips you will be told
why rather than left waiting.

## Scope

**In scope** — anything in this repository:

- authentication and session handling (`backend/app/api/endpoints/auth.py`,
  JWT issuance, JTI blacklisting, cookie flags);
- authorization and tenant isolation — any path where one tenant can reach
  another tenant's data;
- injection of any kind (SQL, command, template, YARA rule, LLM prompt
  injection that escalates to tool execution);
- the ingest webhook and the Celery task boundary;
- secret handling, container hardening, and the `docker-compose.yml` defaults;
- SSRF via the outbound integrations (Ahmia, Shodan, Telegram, SOAR webhooks).

**Out of scope:**

- vulnerabilities in third-party services NASO queries — report those to their
  maintainers;
- findings that require an already-compromised host or an already-authenticated
  administrator;
- missing hardening headers on the documentation site, which is static content;
- results from automated scanners with no demonstrated impact;
- social engineering, physical attacks, and denial of service by volume.

## Safe harbour

We will not pursue or support legal action against anyone who, in good faith:

- reports through the channels above and gives us reasonable time to fix;
- tests only against their own installation;
- does not access, modify, or exfiltrate data belonging to anyone else;
- does not degrade the availability of anyone else's system.

Testing against a third party's NASO deployment without their written
authorisation is outside this safe harbour and may be a criminal offence. See
[LEGAL.md](LEGAL.md).

## Operator responsibilities

The published `docker-compose.yml` is a development and evaluation baseline. It
is not a production configuration. Before running NASO against real data,
operators are expected to:

- generate their own secrets (`python cli/generate_secrets.py`) and never reuse
  the values from `.env.example`. `.secrets-mock/` is written as a 0755
  directory of 0444 files, mirroring how Docker mounts real secrets, so that a
  `cap_drop: ALL` container — which has no CAP_DAC_OVERRIDE and so cannot
  ignore file permissions — can read them regardless of which host user
  created them. That is appropriate for development credentials on a
  developer's own machine and is **not** a production secret store: in
  production, mount real Docker secrets or a secret manager at `/run/secrets`;
- set `NASO_COOKIE_SECURE=true` and terminate TLS in front of the API;
- restrict `ALLOWED_CORS_ORIGINS` to the real frontend origin;
- keep the exposed ports (Jaeger `16686`, MinIO console, RabbitMQ management)
  off any untrusted network;
- rebuild the Tor images with your own control-port password —
  `infrastructure/tor/Dockerfile.tor` defaults to `naso-dev`, which must be
  overridden in tandem with the worker's
  `NASO_DARKWEB_TOR_CONTROL_PASSWORD`:

  ```
  docker compose build --build-arg TOR_CONTROL_PASSWORD=<strong-pw>
  ```

- be aware that the application containers currently run as **root** inside
  the container. `cap_drop: ALL`, `no-new-privileges:true`, and a `read_only`
  root filesystem limit what that buys an attacker, but a dedicated non-root
  UID is not yet in place. Treat container escape as a live risk and do not
  run the stack on a host that carries anything else you care about;
- do not apply `docker-compose.lxc.yml` unless your host genuinely needs it —
  it restores capabilities to Postgres, Redis, and RabbitMQ;
- treat the database as containing personal data — see [LEGAL.md](LEGAL.md).
