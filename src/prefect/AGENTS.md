# Core Prefect SDK

The foundation for building and executing workflows with Python. This covers the SDK layer — decorators, engines, state management, and client-side abstractions.

## Public API

There is no formal public/private boundary beyond the `_` prefix convention. Modules and functions prefixed with `_` are internal. Everything else is considered public and requires backward compatibility.

## Entry Points

- `flows.py` / `tasks.py` — `@flow` and `@task` decorator definitions. The primary user-facing API.
- `flow_engine.py` / `task_engine.py` — Async execution engines that orchestrate runs. **Critical invariant:** both sync and async engine paths must be kept in lockstep. Changes to one must be mirrored in the other.
- `states.py` — State objects and transition logic
- `results.py` — Result persistence and retrieval
- `futures.py` — `PrefectFuture` for async task results
- `task_runners.py` — Task runner implementations (`ThreadPoolTaskRunner`, `ProcessPoolTaskRunner`)
- `transactions.py` — Transaction support
- `context.py` — Runtime context management and dependency injection

## Key Contracts

- **Engine ordering matters.** The engines apply features (retries, caching, result persistence, transactions) in a specific order. Changing the order or forgetting a feature in one engine path is the most common source of breakage.
- **Sync and async must stay in sync.** Both `flow_engine.py` and `task_engine.py` have sync and async paths. Any behavior change must be applied to both.
- **Flow and task engines advance state differently.** The flow engine makes blocking API calls to the server to propose and advance states. The task engine emits `prefect.task_run.*` events (delivered via WebSockets) but advances state locally through `set_state` calls with polling/backoff — do not assume the two engines work the same way.
- **Flow state transitions go through the server.** The flow engine proposes states to the server, which accepts or rejects them via orchestration rules. The task engine, by contrast, manages state transitions locally via `set_state` and emits `prefect.task_run.*` events — it does not propose states to the server.
- **`ProcessPoolTaskRunner` requires picklable data across subprocess boundaries.** `PrefectFuture` objects are not picklable and cannot be passed to worker subprocesses. Any `wait_for` futures must be waited on in the parent process and converted to `State` objects before submission. The subprocess task engine handles `State` objects via `resolve_to_final_result`, which raises `UpstreamTaskError` for non-completed upstreams.

## Logging

Use `get_logger()` from `prefect.logging` instead of raw `logging.getLogger()` — it adds API key obfuscation and places loggers under the `"prefect."` namespace.

- General library code → `get_logger(__name__)`
- SDK core modules (flows, tasks, engine) → `get_logger("flows")`, `get_logger("engine")`, etc.
- Worker implementations → `get_worker_logger(self)`
- Infrastructure orchestrating a run (engines) → `flow_run_logger(flow_run)` / `task_run_logger(task_run)`
- Workers/runners needing child loggers → `.getChild("worker"|"runner", extra={...})` on a run logger
- Code that may run inside or outside a run (concurrency, transactions, blocks) → try `get_run_logger()`, fall back to `get_logger(...)`
- Raw `logging.getLogger()` only inside `src/prefect/logging/` (circular imports) or configuring third-party loggers

## Related

- `client/` → HTTP client for server communication (see client/AGENTS.md)
- `server/` → Orchestration backend (see server/AGENTS.md)
- `cli/` → Command-line interface (see cli/AGENTS.md)
- `events/` → Event system and automations (see events/AGENTS.md)
- `settings/` → Configuration system (see settings/AGENTS.md)
- `concurrency/` → Concurrency slot acquisition and lease management (see concurrency/AGENTS.md)
- `logging/` → Logging handlers, API log shipping, and run-context loggers (see logging/AGENTS.md)
- `runner/` → Thin facade over extracted single-responsibility classes for local flow run execution (see runner/AGENTS.md)
- `deployments/` → YAML-driven deployment lifecycle: project init, build/push/pull steps, and triggering remote flow runs (see deployments/AGENTS.md)
- `docker/` → `DockerImage` class for building and pushing Docker images during deployment
- `telemetry/` → OS-level resource metric collection and run telemetry
