# Workers

Work-pool-based execution layer that polls for flow runs and submits them to infrastructure.

## Purpose & Scope

Workers are long-running processes that pull scheduled flow runs from a work pool and dispatch them to infrastructure (processes, Docker, Kubernetes, cloud VMs, etc.). Each worker type subclasses `BaseWorker` and provides a `BaseJobConfiguration` subclass plus a `run()` method.

This module does NOT manage the Runner execution model (no work pool) — see `runner/AGENTS.md` for that.

## Key Classes

- `BaseWorker` — abstract base; handles heartbeating, polling, cancellation, and attribution env vars
- `BaseJobConfiguration` — Pydantic model for per-run infrastructure config; `prepare_for_flow_run()` stamps attribution variables into `env`
- `ProcessWorker` (`process.py`) — runs flow runs as local subprocesses via `Runner.execute_bundle()`
- `BaseWorkerResult` — result returned by `run()`; wraps infrastructure status codes

## Worker Channel

`BaseWorker.sync_with_backend()` is a thin boundary: it ensures a `WorkerChannel` exists and delegates to `_worker_channel.WorkPoolWorkerChannel.sync(...)`. The channel owns the WebSocket-first path and the REST fallback path, including work-pool read/create/template repair and worker heartbeat. Scheduled flow-run polling remains REST-based.

**Anti-pattern**: Do not split heartbeat or work-pool sync responsibility back into `BaseWorker`; keep sync ownership at the channel boundary.

## Attribution Env Vars

Workers stamp two env vars into `os.environ` for their own process, so all API requests include attribution headers:

- `PREFECT__WORKER_NAME` — set in `setup()` immediately
- `PREFECT__WORKER_ID` — set only when the server returns a non-None `worker_id` in the ready frame. The OSS server always returns `worker_id=None` (the worker is recorded in the DB with a real ID, but that ID is not sent back), so this var is never set on OSS — only Prefect Cloud returns a non-None `worker_id`.

**Teardown guard**: `teardown()` only removes these vars if they still match the current worker instance (`os.environ.get("PREFECT__WORKER_NAME") == self.name`). This prevents a second worker sharing the same process from having its vars cleared.

These are separate from the per-flow-run attribution vars injected into the child process environment by `prepare_for_flow_run(worker_name=..., worker_id=...)`.

## Bundle Launcher Override

When a flow is decorated with an infrastructure decorator (`@docker`, `@ecs`, `@kubernetes`, etc.) and a `launcher` argument is supplied, `InfrastructureBoundFlow` stores a normalized `BundleLauncherOverride` on `flow.launcher`. `BaseWorker.submit()` extracts this via `getattr(flow, "launcher", None)` and calls `resolve_bundle_step_with_launcher(step, launcher, side)` before converting steps to commands.

**Non-obvious:** the launcher replaces the `uv run ...` prefix entirely. With a launcher, the resulting command is `[*launcher, "-m", "<module>", "--key", "<path>"]` rather than `["uv", "run", "--with", "...", "--python", "X.Y", "-m", "<module>", "--key", "<path>"]`. Launchers and `requires` are mutually exclusive — `convert_step_to_command` raises `ValueError` if a step has both.

Work-pool-level launchers are configured via `prefect work-pool storage configure s3|gcs|azure --launcher <executable>` and are stored in the step dict itself. Flow-level launchers (via the decorator) are resolved at submit time and win over the work-pool step configuration.

## Anti-Patterns

- Do not set `PREFECT__WORKER_NAME` / `PREFECT__WORKER_ID` in `os.environ` from outside `BaseWorker` — setup/teardown own this lifecycle.
- Do not call `prepare_for_flow_run()` without passing `worker_name` and `worker_id` — omitting them silently drops attribution from child-process API requests.

## Pitfalls

- `backend_id` is always `None` on the OSS server throughout the entire worker lifecycle — the ready frame deliberately returns `worker_id=None` even though the worker is recorded in the DB with a real ID. Do not use `backend_id is not None` as a proxy for channel health. `PREFECT__WORKER_ID` is never set on OSS; only Prefect Cloud returns a non-None `worker_id` in the ready frame.
- `ProcessWorker` calls the deprecated `Runner.execute_flow_run()` / `Runner.execute_bundle()` paths (suppressing `PrefectDeprecationWarning` with `warnings.catch_warnings()`). It bypasses `FlowRunExecutor` and `ProcessStarter` — this is a known migration gap (see `runner/AGENTS.md`).

## Related

- `runner/AGENTS.md` — Runner execution model (no work pool, local deployments)
- `src/prefect/client/AGENTS.md` — attribution headers set from these env vars
