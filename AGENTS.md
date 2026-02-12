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

- Python 3.10+ with modern typing (`list[int]`, `T | None`)
- Private implementation details (`_private_method`)
- No public API changes without approval
- Use `uv` for dependency management, not `pip`
- Do not use deferred imports (imports inside functions) unless absolutely necessary to avoid circular imports or for optional dependencies

### Logging

Always use Prefect's logging utilities from `prefect.logging` instead of raw `logging.getLogger()`. Prefect's `get_logger()` adds API key obfuscation and places loggers under the `"prefect."` namespace automatically.

**Which logger to use:**

| Context | Function | Import |
|---|---|---|
| Anywhere outside a flow/task run | `get_logger()` | `from prefect.logging import get_logger` |
| Inside a `@flow` or `@task` function | `get_run_logger()` | `from prefect.logging import get_run_logger` |
| Worker implementations | `get_worker_logger()` | `from prefect.logging import get_worker_logger` |

**Logger naming conventions:**
- SDK core modules use short area names: `get_logger("flows")`, `get_logger("engine")`, `get_logger("tasks")`
- Server, client, CLI, and integration code use `__name__`: `get_logger(__name__)`

**When raw `logging.getLogger()` is acceptable:**
- Inside `src/prefect/logging/` itself (avoiding circular imports)
- Configuring third-party library loggers (e.g., uvicorn, sqlalchemy)

**Run loggers and the API log pipeline:**

The `prefect.flow_runs` and `prefect.task_runs` loggers have an `APILogHandler` (configured in `logging.yml`) that batches log records and sends them to `POST /logs/`. `flow_run_logger()` and `task_run_logger()` return a `PrefectLogAdapter` wrapping these loggers, attaching run metadata (`flow_run_id`, `task_run_id`, names) to every record so the API can associate logs with specific runs.

- **Flow/task engines** (`flow_engine.py`, `task_engine.py`) run user code. During `setup_run_context()` they call `flow_run_logger()` / `task_run_logger()` to create the logger available via `get_run_logger()` inside `@flow` and `@task` functions. These logs are sent to the API.
- **Workers** (`workers/base.py`) use `get_worker_logger(self)` for general logging (not sent to API). For per-run logging they call `flow_run_logger(flow_run).getChild("worker", extra={...})`, which inherits the `APILogHandler` and attaches worker context (`worker_name`, `work_pool_name`, `worker_id`).
- **Runners** (`runner/runner.py`) use `get_logger("runner")` for general logging (not sent to API). For per-run logging they call `flow_run_logger(flow_run).getChild("runner", extra={"runner_name": ...})`.

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
- Dependencies: updates to client-side deps in `@pyproject.toml` require parallel changes ing `@client/pyproject.toml`
- AGENTS.md always symlinked to CLAUDE.md
- the redis lease storage lives in @src/integrations/prefect-redis/