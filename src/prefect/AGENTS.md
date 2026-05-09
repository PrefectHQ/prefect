# Core Prefect SDK

The foundation for building and executing workflows with Python. This covers the SDK layer — decorators, engines, state management, and client-side abstractions.

## Public API

There is no formal public/private boundary beyond the `_` prefix convention. Modules and functions prefixed with `_` are internal. Everything else is considered public and requires backward compatibility.

## Entry Points

- `flows.py` / `tasks.py` — `@flow` and `@task` decorator definitions. The primary user-facing API.
- `flow_engine.py` / `task_engine.py` — Async execution engines that orchestrate runs. **Critical invariant:** both sync and async engine paths must be kept in lockstep. Changes to one must be mirrored in the other.
- `flow_engine.py` is also a subprocess entrypoint: `python -m prefect.flow_engine <entrypoint>`. Reads `PREFECT__FLOW_RUN_ID` from the environment; accepts exactly one argument (the flow entrypoint path or module ref). Workers and infrastructure use this to launch flow runs as isolated subprocesses. Plain functions not decorated with `@flow` are auto-converted to flows at this entry point.
- `states.py` — State objects and transition logic
- `results.py` — Result persistence and retrieval
- `futures.py` — `PrefectFuture` for async task results
- `task_runners.py` — Task runner implementations (`ThreadPoolTaskRunner`, `ProcessPoolTaskRunner`)
- `transactions.py` — Transaction support
- `context.py` — Runtime context management and dependency injection

## Key Contracts

- **Engine ordering matters.** The engines apply features (retries, caching, result persistence, transactions) in a specific order. Changing the order or forgetting a feature in one engine path is the most common source of breakage.
- **Set run metadata before state transitions.** Any run attribute that event subscribers observe at the moment of a state transition (e.g., custom `flow_run_name`) must be persisted to the server *before* `set_state()` is called for that transition. Metadata set after the call appears stale to subscribers of that state event.
- **Sync and async must stay in sync.** Both `flow_engine.py` and `task_engine.py` have sync and async paths. Any behavior change must be applied to both.
- **Use `whenever` compat helpers for all datetime conversions on Python 3.13+.** `types/_datetime.py` provides `now()`, `_whenever_to_stdlib()`, `_whenever_zdt_from_py()`, and `_whenever_pdt_from_py()` to abstract over API differences between whenever 0.7.x–0.9.x and ≥ 0.10.0. The `_WHENEVER_NEW_API` flag (True when whenever ≥ 0.10.0) guards version-specific code. Never call `DateTime.now()` or `pendulum.now()` directly — use `now()` from `types/_datetime.py` instead. Never call `ZonedDateTime.from_py_datetime()`, `PlainDateTime.from_py_datetime()`, or `.py_datetime()` directly — use the helpers instead. Violations will silently break on whichever whenever version the helpers weren't written for.
- **Flow and task engines advance state differently.** The flow engine makes blocking API calls to the server to propose and advance states. The task engine emits `prefect.task_run.*` events (delivered via WebSockets) but advances state locally through `set_state` calls with polling/backoff — do not assume the two engines work the same way.
- **Flow state transitions go through the server.** The flow engine proposes states to the server, which accepts or rejects them via orchestration rules. The task engine, by contrast, manages state transitions locally via `set_state` and emits `prefect.task_run.*` events — it does not propose states to the server.
- **`ProcessPoolTaskRunner` requires picklable data across subprocess boundaries.** `PrefectFuture` objects are not picklable and cannot be passed to worker subprocesses. Any `wait_for` futures must be waited on in the parent process and converted to `State` objects before submission. The subprocess task engine handles `State` objects via `resolve_to_final_result`, which raises `UpstreamTaskError` for non-completed upstreams.
- **`ProcessPoolTaskRunner` instances may be deserialized without `__init__` running.** When a runner is pickled and restored in a subprocess, `__init__` is not called, so instance attributes set there may be absent. Access any such attribute via `getattr(self, "_attr", default)` rather than `self._attr` directly — both in the property getter and in `duplicate()`. The `subprocess_message_processor_factories` property demonstrates the required pattern.
- **`ThreadPoolTaskRunner` is cloudpickled when a flow run is dispatched to a subprocess.** `threading.Lock` and other non-picklable thread primitives must be dropped in `__getstate__` and rebuilt in `__setstate__`. Any new instance state added to this class must be evaluated for picklability.
- **Nested task submissions on a bounded `ThreadPoolTaskRunner` can deadlock.** When a worker task submits children and blocks on `.result()` while all `max_workers` threads are busy, the pool starves. `_warn_if_nested_submit_would_deadlock` detects this and emits a one-time warning — preserve this detection when changing pool management.
- **`ResultRecordMetadata` tolerates unknown serializer types.** When loading persisted metadata, an unrecognized serializer `type` is converted to an `UnknownSerializer` placeholder rather than raising `ValidationError`. This allows inspecting result metadata when the serializer implementation is unavailable in the current environment. However, known serializer types with invalid fields still raise `ValidationError`. `UnknownSerializer.dumps()` and `UnknownSerializer.loads()` raise `RuntimeError` — the tolerance is for inspection only, not actual serialization/deserialization.
- **Flow-run suspension is enforced at orchestration boundaries.** Suspension is delivered via `FlowRunSuspensionRequest` and raised with `raise_if_flow_run_suspension_requested()`. When changing engines, futures, task runners, or generator execution, check before returning control to flow user code or proposing a flow state that could leave `Suspended`; keep sync/async paths aligned and avoid per-boundary API reads.

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
- `utilities/` → Cross-cutting helpers: async utils, schema hydration, callables introspection, and more (see utilities/AGENTS.md)
- `blocks/` → Server-persisted configuration objects for external service credentials and settings (see blocks/AGENTS.md)
- `workers/` → Work-pool-based execution layer: polls for flow runs, dispatches to infrastructure (see workers/AGENTS.md)
- `bundles/` → Flow bundling for remote execution (`create_bundle_for_flow_run`, cloudpickle+gzip); used by workers when dispatching `InfrastructureBoundFlow` runs; `execute_bundle_from_file` is lazy-loaded via `__getattr__` to avoid `runpy` warnings when invoked as `python -m prefect.bundles.execute`
- `plugins.py` → Stable public surface for startup hooks and `prefect.collections` entrypoint loading; pluggy symbols are lazy-loaded so `prefect-client` builds (which don't ship pluggy) can still import `load_prefect_collections` without error
- `docker/` → `DockerImage` class for building and pushing Docker images during deployment
- `telemetry/` → OS-level resource metric collection and run telemetry
- `testing/` → Test utilities shipped with the SDK: `prefect_test_harness`, assertion helpers, and reusable fixtures (see testing/AGENTS.md)
