Prefect is a workflow orchestration platform that coordinates and observes data pipelines. It provides a Python SDK for building workflows, a server backend for orchestration, and a web-based UI for managing and monitoring workflows.

# Guiding Principles

Your primary responsibility is to the project and its users. Every change should serve the broader user base — not just the immediate request. Be a quality gate: prefer correct, minimal, well-tested changes over fast ones.

# Directory Structure

```
prefect/
├── benches/                         # Benchmarks (CLI, flows, tasks, imports)
├── client/                          # prefect-client build: subset of src/prefect/ published as a separate PyPI package
├── compat-tests/                    # Tests for REST API compatibility with Prefect Cloud
├── Dockerfile                       # Production container image
├── docs/                            # Mintlify documentation (see docs/AGENTS.md)
├── examples/                        # Example flows (auto-published to docs)
├── integration-tests/               # End-to-end integration tests (require running server)
├── justfile                         # Task runner (just <command>)
├── load_testing/                    # Load/performance testing
├── plans/                           # Design/implementation plan documents
├── pyproject.toml                   # Root package config
├── schemas/                         # JSON schemas (prefect.yaml, settings)
├── scripts/                         # Code generation and release scripts
├── src/
│   ├── integrations/                # External service integrations (see src/integrations/AGENTS.md)
│   └── prefect/                     # Core package: SDK, server, CLI (see src/prefect/AGENTS.md)
├── tests/                           # Test suite, mirrors src/prefect/ (see tests/AGENTS.md)
├── tools/                           # Build tools
├── ui/                              # Vue UI (legacy, will be replaced by ui-v2)
├── ui-v2/                           # React UI rewrite (see ui-v2/AGENTS.md)
└── uv.lock                          # Lockfile (auto-generated, do not edit manually)
```

# Essential Commands

```bash
# Dependencies
uv sync                                # Install all dev dependencies
just install                           # Same as above, plus perf group

# Running code
uv run -s my_script.py                             # Run a script with an editable prefect install
uv run --extra aws repros/1234.py                  # Run repro needing an integration extra
uv run --project ./src/integrations/<name> <cmd>   # Run against a local integration from repo root
prefect server start                               # Start local server
prefect config view                                # Inspect current configuration

# Testing (see tests/AGENTS.md for full details)
uv run pytest tests/path.py -k name    # Run specific test
uv run pytest tests/path.py -x -n4     # Parallel, stop on first failure

# Linting & formatting
uv run ruff check --fix .              # Lint with auto-fix
uv run ruff format .                   # Format code
uv run pre-commit run --all-files      # Run all pre-commit hooks

# Docs (from repo root)
just docs                              # Start Mintlify dev server at localhost:3000
just generate-docs                     # Regenerate all doc artifacts

# UI (from repo root)
just ui-v2                             # Start React dev server at localhost:5173

# Docker
docker build -t prefect .                              # Default build (Python 3.10)
docker build --build-arg PYTHON_VERSION=3.12 -t prefect .  # Custom Python version
docker build --build-arg EXTRA_PIP_PACKAGES="prefect-aws" -t prefect .  # With extras
```

## Quick Reference

| Component | Path | Tests |
|-----------|------|-------|
| Core SDK (flows, tasks, states, deployments) | `src/prefect/` | `tests/` |
| Flow & task engines (async orchestration) | `src/prefect/flow_engine.py`, `task_engine.py` | `tests/engine/` |
| Client SDK (schemas, HTTP client) | `src/prefect/client/` | `tests/client/` |
| Server (API, database, scheduling) | `src/prefect/server/` | `tests/server/` |
| CLI | `src/prefect/cli/` | `tests/cli/` |
| Settings | `src/prefect/settings/` | `tests/settings/` |
| Integrations (`prefect-aws`, `prefect-dbt`, etc.) | `src/integrations/` | per-integration |
| React UI (replacing Vue `ui/`) | `ui-v2/` | `ui-v2/e2e/` |

## Tech Stack & Tooling

- **Python >=3.10,<3.15** with modern typing (`list[int]`, `T | None`)
- **FastAPI** for REST APIs
- **Pydantic v2** for validation
- **SQLAlchemy 2.0** async ORM
- **Alembic** for database migrations
- **PostgreSQL/SQLite** databases
- **React + TypeScript** for UI (see ui-v2/AGENTS.md)
- **Ruff** for linting and formatting
- **Pre-commit** hooks: ruff, codespell, mypy (partial), uv-lock, no-commit-to-branch

## Architecture Overview

- **Three user-facing surfaces**: Python SDK (`@flow`/`@task` decorators), CLI (`prefect` command), REST API (FastAPI server)
- **Server is the source of truth for flow state transitions** — the flow engine proposes states, and the server's orchestration layer accepts or rejects them. Task state transitions are managed locally by the task engine via `set_state` and communicated through `prefect.task_run.*` events
- **Two published packages**: `prefect` (full SDK + server) and `prefect-client` (lightweight client subset). `client/` contains the build config that selects which files from `src/prefect/` go into `prefect-client`
- **Integrations are separate PyPI packages** (`prefect-aws`, `prefect-dbt`, etc.) each with their own version, published independently from `src/integrations/`
- **Async-first execution model** with sync wrappers — the engines (`flow_engine.py`, `task_engine.py`) are async; sync `@flow`/`@task` functions are run in workers

## Anti-patterns

- **Never bypass the server for flow state transitions** — always go through the orchestration API, even in tests. Task state transitions are managed locally by the task engine by design
- **Never use `pip install` or `uv pip`** — use `uv` for all dependency management
- **Never use deferred imports** (imports inside functions) unless required to break circular imports or for optional dependencies
- **Never commit directly to `main`** — a pre-commit hook enforces this
- **Never skip pre-commit hooks** (`--no-verify`) — fix the underlying issue instead
- **Never amend commits** (`--amend`) — create new commits instead

# Development Guidelines

## Make sure you have a Prefect server or Prefect Cloud
- use `prefect config view` to check your current profile
- run `prefect server start` in the background if needed

## Code Conventions

- Private implementation details (`_private_method`)
- No public API changes without approval
- Use single backticks for inline code references in docstrings, not double backticks

## Testing

- Directory structure mirrors source code
- Run affected tests after changes: `uv run pytest tests/module/`
- Tests require deterministic behavior
- Mock external dependencies

## Working on Issues

- Read the GitHub issue/PR and comments (`gh issue view`, `gh pr view`) before writing code
- Understand the scope and intended behavior — ask clarifying questions if unclear
- Create reproduction scripts in `repros/` directory (create it if needed; add to `.gitignore`)
- Name files by issue number: `repros/1234.py` (only create one file per issue)
- Ensure the issue is reproducible before fixing
- Add unit tests for fixes
- DO NOT delete files from `repros/` directory after reproducing the issue unless asked

## PR Body Style

- Start with "closes #1234" if resolving issue
- Brief summary: "this PR {changes}"
- Details in `<details>` tag
- Include relevant links

# Project Practices

- All PRs require test coverage for new functionality
- GitHub issues are used for tracking issues (use the `gh` cli)
- Dependencies: updates to client-side deps in `pyproject.toml` require parallel changes in `client/pyproject.toml`
- AGENTS.md always symlinked to CLAUDE.md
