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

## Automated scanning

`.github/workflows/security-scan.yml` runs on every push and pull request to
`main`, and weekly on Monday regardless of activity — the weekly run is the one
that matters, because a new advisory against a transitive dependency arrives
without anyone touching the repository. It covers:

| Scanner | Target | Fails the job on |
|---------|--------|------------------|
| `pip-audit` | the three Python requirement sets | any known advisory |
| `npm audit` | `frontend/` and `docs/` | `high` and above |
| Trivy | both container images | `HIGH`/`CRITICAL` **with a fix available** |
| Gitleaks | the working tree | any credential pattern |

It is a separate workflow from `Draconian NASO CI` on purpose. The merge gate
has to fail only for reasons the pull-request author can fix; folding advisory
scanning into it would mean either red builds nobody can act on, or muted
advisories. Trivy findings with no upstream fix are reported as a SARIF
artifact rather than failing the build, for the same reason.

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
  created them. One rule, no exceptions: Elasticsearch used to need a 0600
  file and now takes its password from `.env` instead, because satisfying both
  constraints on one shared directory was not possible — see the comment in
  `docker-compose.yml`. That is appropriate for development credentials on a
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

- note that the application containers run as a non-root uid 10001 (`naso` in
  the API image, `pwuser` in the worker image) with `cap_drop: ALL`,
  `no-new-privileges:true`, and a `read_only` root filesystem. The datastore
  containers are the exception — see the capability note below;
- note that Postgres, Redis, and RabbitMQ are granted CHOWN, SETUID, SETGID,
  DAC_OVERRIDE, FOWNER and SETFCAP in docker-compose.yml. Their official
  entrypoints need those to chown their data directory and drop from root to
  the service user; without them the containers crash-loop. The API and
  worker containers, which run application code, keep `cap_drop: ALL` with
  nothing added back;
- treat the database as containing personal data — see [LEGAL.md](LEGAL.md).
