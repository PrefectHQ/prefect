Prefect is a workflow orchestration platform that coordinates and observes any data pipeline. It provides a Python SDK for building workflows, a server backend for orchestration, and a React-based UI.

# Directory Structure

```
prefect/
├── benches/                         # Benchmarks (CLI, flows, tasks, imports)
├── client/                          # prefect-client build: stripped-down package published to PyPI alongside prefect
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
├── ui/                              # Vue UI (currently shipped)
├── ui-v2/                           # React UI rewrite (in development, see ui-v2/AGENTS.md)
└── uv.lock                          # Lockfile (auto-generated, do not edit manually)
```

# Essential Commands

```bash
# Dependencies
uv sync                                # Install all dev dependencies
just install                           # Same as above, plus perf group

# Running code
uv run -s my_script.py                 # Run a script with an editable prefect install
uv run --extra aws repros/1234.py      # Run repro needing an integration extra
prefect server start                   # Start local server
prefect config view                    # Inspect current configuration

# Testing
uv run pytest tests/                   # Run all tests
uv run pytest -n4                      # Run tests in parallel
uv run pytest tests/path.py -k name    # Run specific test
uv run pytest tests/path.py -x         # Stop on first failure

# Linting & formatting
uv run ruff check --fix .              # Lint with auto-fix
uv run ruff format .                   # Format code
uv run pre-commit run --all-files      # Run all pre-commit hooks

# Docs (from repo root)
just docs                              # Start Mintlify dev server at localhost:3000
just generate-docs                     # Regenerate all doc artifacts

# UI (from repo root)
just ui-v2                             # Start React dev server at localhost:5173
```

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

# Development Guidelines

## Make sure you have a Prefect server or Prefect Cloud
- use `prefect config view` to check your current profile
- run `prefect server start` in the background if needed

## Code Conventions

- Python >=3.10,<3.15 with modern typing (`list[int]`, `T | None`)
- Private implementation details (`_private_method`)
- No public API changes without approval
- Use `uv` for dependency management, not `pip`
- Do not use deferred imports (imports inside functions) unless absolutely necessary to avoid circular imports or for optional dependencies
- Use single backticks for inline code references in docstrings, not double backticks

## Testing

- Directory structure mirrors source code
- Run affected tests after changes: `uv run pytest tests/module/`
- Tests require deterministic behavior
- Mock external dependencies

## Working on Issues

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
- Pre-commit hooks required (never use `--no-verify`); a hook blocks direct commits to `main`
- Dependencies: updates to client-side deps in `pyproject.toml` require parallel changes in `client/pyproject.toml`
- AGENTS.md always symlinked to CLAUDE.md
