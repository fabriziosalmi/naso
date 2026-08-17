# Contributing to NASO

Thanks for considering a contribution. This document covers how to get a
working development environment, what the quality bar is, and the legal points
you need to be aware of before you open a pull request.

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Before you start

**Security issues do not go here.** If you have found a vulnerability, follow
[SECURITY.md](SECURITY.md) and report it privately. Do not open a public issue
or pull request for it.

**NASO is a dual-use tool.** Read [LEGAL.md](LEGAL.md). Contributions that exist
primarily to enable unauthorised access, mass surveillance, or targeting of
individuals will be declined regardless of code quality.

**Never contribute real data.** Fixtures, tests, screenshots, seed data, and
issue reports must not contain real personal data, real credentials, or excerpts
from real breach corpora — not even redacted ones. Use synthetic values. The
existing fixtures use `.example.com` domains (`acme.example.com`,
`corp.example.com`) and generated identities; follow that convention.
Note that `email-validator` rejects the special-use TLDs `local`, `test`,
`localhost`, `invalid`, `arpa`, and `onion`, so an address under one of
those will fail schema validation. A pull request containing real
personal data will be closed and the branch deleted rather than merged.

## Development setup

Requirements: Docker with Compose v2, Python 3.11, Node 20.

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso

# 1. Generate .secrets-mock/ (docker-compose mounts it at /run/secrets and
#    will not start without it) and render .env with the generated values.
make bootstrap

# 2. Install the pre-commit hooks. They mirror the CI gates and run in about
#    a second, which is cheaper than a seven-minute round trip.
pip install pre-commit && pre-commit install

# 3. Bring up the backing services, API, and workers.
make up
```

`make bootstrap` fills in the credentials for you — it renders `.env` from
`.env.example` substituting the passwords it just generated, so the values the
containers are provisioned with and the ones the application connects with
cannot drift apart. It leaves an existing `.env` alone, so delete the file
first if you want it regenerated. The `CHANGE_ME` values that remain afterwards
are the third-party API keys (Shodan, Telegram), which only matter if you are
working on those integrations.

The frontend is **not** part of the Compose stack — it runs as a Vite dev server
on the host:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Seed synthetic data once the stack is healthy:

```bash
make demo
```

## Running the checks

Run these before you push. They are the same checks CI runs.

```bash
# Python lint + format — must be clean, there is no warning tier
ruff format --check .
ruff check .

# Backend test suite (inside the API container)
docker exec naso-api pytest tests/ -v

# Frontend unit tests
cd frontend && npm run test -- --run

# Frontend end-to-end. Playwright builds the app and serves the bundle itself
# on :5173, every time and in every environment — so this run means the same
# thing on your machine as it does in CI. You do not need `npm run dev`; stop
# it if it is holding :5173, because the port is claimed strictly and preview
# will refuse to start rather than serve something unexpected.
cd frontend && npx playwright test

# Everything at once (this is what `make test` runs)
./cli/validate.sh
```

`ruff format` will fix formatting for you; `ruff check --fix` will fix most lint
findings. Configuration lives in `pyproject.toml` — 120-column lines, double
quotes, and the `E`, `F`, `I`, `UP`, `B`, `SIM` rule sets.

Ruff's version is pinned in three places that must move together:
`.github/workflows/draconian-ci.yml`, `backend/requirements-dev.txt`, and
`.pre-commit-config.yaml`. They have diverged once — CI installed an unpinned
ruff, 0.16 began formatting Python inside Markdown fences, and the gate went
red on a day nobody had touched the code. If you bump one, bump all three in
the same commit.

## Code conventions

- **Python** — async throughout in the API and domain services. Do not
  introduce a blocking call into an async path; if you need one, push it into a
  Celery task. Type hints on public functions.
- **JavaScript/React** — function components, hooks, Zustand for shared state.
  Keep new UI on the existing Radix + Tailwind primitives in
  `frontend/src/components/ui/` rather than adding a component library.
- **Language** — code, comments, docstrings, commit messages, and documentation
  are in **English**. The project previously mixed Italian and English; new
  contributions should not add to that.
- **Layout** — `backend/` is the FastAPI application, `shared/` holds domain
  services and Celery tasks used by both the API and the workers, `workers/`
  holds worker entrypoints. Business logic belongs in `shared/domain/services/`,
  not in an endpoint handler.

## Commits and pull requests

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(correlation): cluster aliases across Tor and clearnet sources
fix(auth): reject a revoked JTI before touching the database
docs(readme): correct the quickstart secret bootstrap
chore(deps): bump elasticsearch to 8.12.2
```

For a pull request:

1. Branch from `main`.
2. Keep it focused — one concern per PR. A refactor bundled with a feature will
   be asked to split.
3. Add or update tests. New domain logic without a test will not be merged.
4. Update the documentation under `docs/` if you changed observable behaviour.
5. Make sure the checks above pass locally.
6. Describe **what** changed and **why**. A diff shows the what; the why is what
   review needs.

Expect review comments. This is a small project — response times depend on
maintainer availability, so please be patient rather than bumping the thread.

## Licensing of contributions

NASO is licensed under the [GNU AGPL-3.0](LICENSE). By submitting a
contribution you agree that it is licensed under the same terms and that you
have the right to submit it — that it is your own work, or that you have
permission from the copyright holder.

If you are contributing on behalf of an employer, make sure you have their
authorisation first.

## Reporting bugs and requesting features

Open an issue with:

- what you expected and what actually happened;
- the commit SHA you are on;
- steps to reproduce, ideally against the synthetic seed data;
- relevant logs — **redacted**, since NASO logs touch sensitive material.

For a feature request, describe the operational problem you are trying to solve
before proposing a solution. It is often not the feature you expect.
