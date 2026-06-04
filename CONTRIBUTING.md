# Contributing to NormaCore

By submitting a pull request, you agree to license your contribution under the
[Apache License 2.0](LICENSE).

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker + Compose (for integration tests)

## Getting started

Fork the repository, then clone your fork and set up the dev environment:

```sh
git clone https://github.com/<your-handle>/normacore.git
cd normacore
uv sync
uv run detect-secrets scan > .secrets.baseline
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

Verify hooks are wired correctly:

```bash
uv run pre-commit run --all-files
```

## Branch naming

```sh
type/short-description
type/issue-id-short-description
```

Examples: `feat/pdf-reader`, `fix/42-rrf-score-overflow`, `doc/eval-harness`

## Commit messages

```sh
TYPE: Short description (50 chars or less)

Longer explanation if needed (wrap at 72 chars).
Explain WHY, not WHAT.

- Bullet points okay
- Reference issues: Fixes #123
```

Valid types: `FEAT`, `FIX`, `DOC`, `STYLE`, `REFACTOR`, `TEST`, `PERF`,
`BUILD`, `CI`, `RELEASE`

## Submitting a pull request

- One logical change per PR
- All pre-commit hooks must pass before opening the PR
- Tests must pass: `uv run pytest`
- Update `CHANGELOG.md` in the same commit as your code change (see
  [Keep a Changelog](https://keepachangelog.com/))
- PRs go against `main`; `main` is always releasable

## Reporting issues

Use GitHub Issues for bugs and feature requests. For security vulnerabilities,
see [SECURITY.md](SECURITY.md).
