# Client SDK

HTTP client for communicating with Prefect server and Prefect Cloud.

## Key Contracts

- **All client methods live on orchestration submodules** — not on the main client class directly. The main `PrefectClient` (async) and `SyncPrefectClient` compose these domain-specific clients.
- **Every method must have both sync and async variants.** Each orchestration submodule exposes paired clients (e.g., `ArtifactClient` and `ArtifactAsyncClient`).
- **Methods should accept simple kwargs** (`str`, `int`, `UUID`, etc.) and return Pydantic models. Avoid accepting complex objects as parameters.
- **Client schemas are separate from server schemas.** This module has its own `schemas/` to avoid tangling with `server/schemas/`. Keep the boundary clean.
- **Do not import server-only modules** (`server/database`, `server/models`, etc.) from anything in this directory — it would break the `prefect-client` package build.
- **Task-run submission schemas must be eagerly rebuilt.** Schemas instantiated on the concurrent submission path (`Task.create_local_run()`) are rebuilt at import time via `model_rebuild()` at the bottom of `schemas/objects.py`. Pydantic defers schema construction to first use; under threadpool contention, multiple workers race to build the same schema simultaneously. If you add a new schema used in this hot path, add a corresponding `model_rebuild()` call there.

## Structure

- `orchestration/` — Domain-specific API submodules (`_flows/`, `_deployments/`, `_work_pools/`, etc.)
- `orchestration/base.py` — Base client with HTTP transport
- `orchestration/routes.py` — API route constants
- `schemas/` — Client-side Pydantic models (actions, filters, objects, responses, schedules, sorting)
- `cloud.py` — Prefect Cloud-specific extensions (workspaces, RBAC)
- `subscriptions.py` — WebSocket subscription client
- `_version_checking.py` — Shared server version compatibility check (once-per-process, keyed by `(api_url, client_version)`). Used by HTTP clients and WebSocket clients (`events/clients.py`, `logging/clients.py`). When adding a new client type that connects to the server, call `check_server_version` from here rather than reimplementing the check.

## Related

- `server/schemas/` → Server-side request/response models (separate from `client/schemas/`)
- Top-level `client/` → Build config for `prefect-client` PyPI package (see client/AGENTS.md at repo root)
