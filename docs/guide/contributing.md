# Contributing

The authoritative contribution guide lives in the repository, at
[CONTRIBUTING.md](https://github.com/fabriziosalmi/naso/blob/main/CONTRIBUTING.md).
It is not duplicated here — two copies of a process document drift, and the one
in the repository is the one a contributor reads next to the code.

This page covers what you need before you get there.

## Three things to read first

**[SECURITY.md](https://github.com/fabriziosalmi/naso/blob/main/SECURITY.md)** —
if you have found a vulnerability, it does not go in a pull request or a public
issue. Report it privately through a GitHub security advisory.

**[LEGAL.md](https://github.com/fabriziosalmi/naso/blob/main/LEGAL.md)** — NASO
is dual-use. Contributions that exist primarily to enable unauthorised access,
mass surveillance, or the targeting of individuals will be declined regardless
of how good the code is.

**Never contribute real data.** No real personal data, credentials, or excerpts
from real breach corpora — in fixtures, tests, screenshots, seed data or issue
reports, redacted or not. Use synthetic values under `.example.com`, matching
the existing fixtures. Note that `email-validator` rejects the special-use TLDs
`local`, `test`, `localhost`, `invalid`, `arpa` and `onion`, so an address
under one of those will fail schema validation anyway. A pull request
containing real personal data is closed and its branch deleted, not merged.

## Getting a working environment

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso
make bootstrap                              # secrets + .env
pip install pre-commit && pre-commit install
make up
cd frontend && npm install && npm run dev   # the SPA is not in Compose
```

See [Deployment](/guide/deployment) for what each service does and
[Configuration](/guide/configuration) for where settings come from. When
something does not start, [the runbook](/guide/runbook) covers the failure
modes that have actually happened here.

## The quality bar

```bash
ruff format --check . && ruff check .   # no warning tier; clean or not
./cli/validate.sh                       # == make test; what CI runs
```

The pre-commit hooks run the same ruff version CI installs, plus secret
detection and parse checks, in about a second. Installing them is the
difference between finding a problem now and finding it seven minutes into a
CI run.

Four expectations that come up in review more than any others:

- **One concern per pull request.** A refactor bundled with a feature gets
  asked to split.
- **New domain logic ships with tests.** Not negotiable.
- **Business logic belongs in `shared/domain/services/`**, not in an endpoint
  handler.
- **Explain the *why*.** The diff already shows the what.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
Code, comments and documentation are in English — the project has some
historical Italian in it, and new contributions should not add to that.

## Contributions are AGPL-3.0

By submitting one you agree it is licensed under the same terms as the project
and that you have the right to submit it. If you are contributing on behalf of
an employer, confirm you have their authorisation first.
