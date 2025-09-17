# AGENTS.md

This file provides guidance to AI assistants when working with this repository.

## Project Overview

Prefect is a workflow orchestration platform that coordinates and observes any data pipeline. It provides an SDK for building workflows and a server/cloud backend for orchestration.

Components:

- `src/prefect/` (@src/prefect/, @tests/): Core SDK - flows, tasks, states, deployments
- `src/prefect/engine.py` (@src/prefect/engine.py): Engine - orchestration entrypoint
- `src/prefect/client/` (@src/prefect/client/, @tests/client/): Client SDK - client, schemas, utilities
- `src/prefect/server/` (@src/prefect/server/, @tests/server/): Orchestration server - API, database, scheduling
- `src/integrations/` (@src/integrations/: External service integrations

## Essential Commands

```bash
uv sync                         # Install dependencies
uv run --extra aws repros/1234.py  # Run repro related to prefect-aws
uv run pytest tests/            # Run tests
uv run pytest -n4              # Run tests in parallel
uv run pytest tests/some_file.py -k test_name  # Run specific test
prefect server start           # Start local server
prefect config view            # Inspect configuration
```

## Tech Stack

- **FastAPI** for REST APIs
- **Pydantic v2** for validation
- **SQLAlchemy 2.0** async ORM
- **Alembic** for migrations
- **PostgreSQL/SQLite** databases

## Development Guidelines

### Make sure you have a Prefect server or Prefect Cloud
- use `prefect config view` to check your current profile
- run `prefect server start` in the background if needed


### Code Conventions

- Python 3.9+ with modern typing (`list[int]`, `T | None`)
- Private implementation details (`_private_method`)
- No public API changes without approval
- Use `uv` for dependency management, not `pip`

### Testing

- Directory structure mirrors source code
- Run affected tests after changes: `uv run pytest tests/module/`
- Tests require deterministic behavior
- Mock external dependencies

### Working on Issues

- Create repros in `repros/` directory (gitignored)
- Name files by issue number: `repros/1234.py` (only create one file per issue)
- Reproduce before fixing
- Add unit tests for fixes
- DO NOT delete files from `repros/` directory after reproducing the issue unless asked

### PR Style

- Start with "closes #1234" if resolving issue
- Brief summary: "this PR {changes}"
- Details in `<details>` tag
- Include relevant links

## Project Practices

- GitHub issues are used for tracking issues (use the `gh` cli)
- Pre-commit hooks required (never use `--no-verify`)
- There are some slower pre-push hooks that may modify files on `git push`; when that happens, run `git commit --amend` to bring those into the prior commit (never use `--amend` in any other situation unless asked)
- Dependencies: updates to client-side deps in `@pyproject.toml` require parallel changes ing `@client/pyproject.toml`
- AGENTS.md always symlinked to CLAUDE.md
- the redis lease storage lives in @src/integrations/prefect-redis/