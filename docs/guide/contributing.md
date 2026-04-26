# Contributing

NASO is a small project; contributions land directly on `main` after PR review. No CLA, no contributor license — the project is MIT-licensed and a PR signals you accept that.

## Local setup

```bash
git clone https://github.com/fabriziosalmi/naso.git
cd naso
make bootstrap
pip install pre-commit && pre-commit install      # ruff + actionlint + hygiene per-commit
```

Optional but recommended: a Python 3.11 venv pointing at `backend/requirements.txt + workers/requirements.txt + shared/requirements-shared.txt`. The CI matrix runs against 3.11 only.

## Running things

| Command                       | What it does                                                                |
|-------------------------------|------------------------------------------------------------------------------|
| `make up`                     | docker compose up -d                                                         |
| `make down`                   | Tear it all down                                                             |
| `make logs`                   | Tail backend + worker-pipeline                                               |
| `make demo`                   | Seed *Operation Lazarus* synthetic data                                      |
| `make test`                   | Backend pytest in container + frontend vitest on host                        |
| `./cli/validate.sh`           | Same as `make test` plus playwright e2e — what CI gates on                   |
| `ruff check . && ruff format --check .` | Same lint gate as CI                                              |

## Code style

- **Python**: ruff handles both linting and formatting. The full config lives in [`pyproject.toml`](https://github.com/fabriziosalmi/naso/blob/main/pyproject.toml). Targets `py311`. Line length 120. No black, no isort — ruff format covers both.
- **JavaScript/JSX**: there's no committed ESLint config yet. Match the surrounding style; the pre-commit hook is informational for now.
- **Imports**: ruff's isort sorts them. Module-level imports go at the top (`E402` is on); `# noqa: E402` is reserved for the worker tracing dance.
- **Type hints**: `from __future__ import annotations` is fine but not required. PEP 604 (`X | None`) is preferred over `Optional[X]` since the bump to py311.

## Comments and docstrings

- Default to no comment. Code that needs an inline explanation usually needs better names instead.
- Write a comment when the *why* isn't obvious from the code: a workaround for a specific upstream bug, a non-obvious invariant, a hidden constraint, behaviour that would surprise a reader. Always say *why*, never just *what*.
- Don't reference the current task / fix / caller — those rot ("added for the merge-engine work") and aren't useful in a year.
- Docstrings on public functions and middleware classes only; ruff doesn't enforce a docstring convention.

## Tests

- Backend: pytest, in-memory SQLite via `conftest.py`. New tests should use `@pytest_asyncio.fixture` for async fixtures (the `@pytest.fixture async def` form is deprecated in pytest-asyncio 0.21+). Reference: `backend/tests/conftest.py`.
- Frontend: vitest. Match the structure in `frontend/src/store/useNasoStore.test.js`.
- E2E: Playwright. New scenarios go in `frontend/tests/e2e/`. Don't sprinkle specs anywhere else (an orphan in `frontend/e2e/` was running nowhere for months — see commit `49e9d47`).

The CI runs ruff first; if your PR is red on ruff, the rest of the matrix doesn't even start.

## Commit messages

We follow Conventional Commits loosely: `<type>(<scope>): <subject>`. Types we use:

| Prefix     | When                                                       |
|------------|------------------------------------------------------------|
| `feat:`    | New user-visible behavior                                  |
| `fix:`     | Bug fix                                                    |
| `chore:`   | Tooling, deps, lint, hygiene                               |
| `docs:`    | Documentation only                                         |
| `test:`    | Test infrastructure                                        |
| `style:`   | Pure formatting (very rare; ruff format covers most)       |
| `ci:`      | Workflow changes                                           |

Subject in present tense, imperative, lower-case, no trailing dot. The body explains *why*, not *what* — the diff is the *what*. Example:

```
feat(audit): paginate /system/audit and fix verify_chain count

GET /system/audit hard-coded LIMIT 100 with no pagination knob and
no filter, so the UI's "load more" was impossible and a script
wanting the full history had no way to ask for it. The
verify_audit_chain endpoint counted rows by materializing every
AuditLog into Python memory, which is quadratic with how often the
AuditIntegrityBanner re-runs verify across route changes.

Backend changes:
  - GET /audit grows query params: limit, offset, action,
    resource_type. Response is now {total, limit, offset, items}.
  - verify_chain endpoint: replace len(all_rows) with
    select(func.count()).
```

A diff-friendly explanation up front, then the bullet list. Look at the `git log` for the last 30-50 commits for the cadence we want.

## Pull request checklist

Before opening:

- [ ] `ruff check .` and `ruff format --check .` are clean.
- [ ] `make test` passes locally (or you say why it can't be run, e.g. requires Docker).
- [ ] You added or updated a test for the behavior change.
- [ ] If you touched `Settings`, you added the new field to [`docs/guide/configuration.md`](configuration.md).
- [ ] If you changed an exposed endpoint, you updated [`docs/api/index.md`](../api/index.md).
- [ ] Commit messages follow the convention above.

The PR description should answer:

1. What this changes (1-2 sentences).
2. Why — link the issue, paste the failure, or the reasoning.
3. How to verify locally.

A self-contained PR with one of those each is reviewed in hours; a 600-line drive-by takes weeks.

## Reporting bugs / vulnerabilities

- **Bugs**: open a GitHub issue with reproduction steps. The triage map in the [Runbook](runbook.md) is a good first stop to confirm the bug isn't an env issue.
- **Security**: don't open a public issue. Use GitHub's "Report a vulnerability" private advisory or email the maintainer. Allow 30 days for a fix before public disclosure. The [security model](security.md) describes the threat surface in scope.

## License

By contributing you agree your changes are released under the project's [MIT License](https://github.com/fabriziosalmi/naso/blob/main/LICENSE).
