# Runner

Thin facade over single-responsibility extracted classes. New behavior belongs in the extracted classes, not the Runner.

## Architecture

`Runner` (runner.py) delegates to these classes:

| Class | File | Responsibility |
|---|---|---|
| FlowRunExecutor | _flow_run_executor.py | Per-run lifecycle: submitting -> start -> wait -> crashed/hooks |
| ProcessManager | _process_manager.py | Process map, PID tracking, kill with SIGTERM->SIGKILL |
| StateProposer | _state_proposer.py | All API state transition proposals |
| CancellationManager | _cancellation_manager.py | Kill -> hooks -> state -> event cancellation sequence |
| HookRunner | _hook_runner.py | on_cancellation / on_crashed hook execution |
| EventEmitter | _event_emitter.py | Event emission via EventsClient; degrades to NullEventsClient on WebSocket rejection |
| LimitManager | _limit_manager.py | Concurrency limiting |
| DeploymentRegistry | _deployment_registry.py | Deployment/flow/storage/bundle maps |
| ScheduledRunPoller | _scheduled_run_poller.py | Poll loop, run discovery, scheduling |
| ProcessStarter (protocol) | _flow_run_executor.py | Strategy interface for starting processes |
| FlowRunExecutorContext | _flow_run_executor.py | Async context manager for one-shot execution outside Runner (CLI, bundles) |
| DirectSubprocessStarter | _starter_direct.py | Runs Flow object via run_flow_in_subprocess |
| EngineCommandStarter | _starter_engine.py | Spawns `python -m prefect.engine` subprocess |
| BundleExecutionStarter | _starter_bundle.py | Executes serialized bundle in SpawnProcess |

## Key Contracts

**New behavior goes in the extracted class, not the facade.** If you're fixing or adding:
- Process lifecycle -> ProcessManager or FlowRunExecutor
- State transitions -> StateProposer
- Shutdown/crash handling -> FlowRunExecutor.submit()
- Cancellation -> CancellationManager
- Hooks -> HookRunner

**Legacy methods on Runner exist only for backward compatibility.** Do not add new behavior to:
- `_submit_run_and_capture_errors()` -- replaced by FlowRunExecutor.submit()
- `_run_process()` -- replaced by ProcessStarter implementations
- `_flow_run_process_map` dict -- replaced by ProcessManager
- `_kill_process()` -- replaced by ProcessManager.kill()
- `_run_on_crashed_hooks()` / `_run_on_cancellation_hooks()` -- replaced by HookRunner
- `execute_flow_run()` -- deprecated (Mar 2026); use `FlowRunExecutorContext` + `EngineCommandStarter`
- `execute_bundle()` -- deprecated (Mar 2026); use `execute_bundle()` from `prefect._experimental.bundles.execute`
- `reschedule_current_flow_runs()` -- deprecated (Mar 2026); SIGTERM rescheduling is now handled inline by the CLI execute path

These will be removed once internal callers (notably ProcessWorker) are migrated. ProcessWorker currently suppresses the deprecation warnings via `warnings.catch_warnings()`.

## EventEmitter WebSocket Degradation

`EventEmitter.__aenter__` catches `websockets.exceptions.InvalidStatus` (HTTP 4xx rejections) and silently swaps the failed client for a `NullEventsClient`. This handles old clients (≤3.6.13) connecting to servers ≥3.6.14 with `PREFECT_SERVER_API_AUTH_STRING` configured — the server rejects the WebSocket handshake, but events are non-critical telemetry so the flow run must not crash. A `WARNING` is logged. If `__aenter__` raises, `__aexit__` is **not** called on the original client (it was never successfully entered); the replacement `NullEventsClient` is entered instead.

## AsyncExitStack LIFO Ordering

Services enter in this order during `Runner.__aenter__` (teardown is exact reverse):

1. client -- exits LAST (needed by all services)
2. process_manager -- exits 5th (kills remaining after runs finish)
3. limit_manager -- exits 4th
4. event_emitter -- exits 3rd (flush events before client closes)
5. runs_task_group -- exits 2nd (wait for in-flight runs to complete)
6. cancelling_observer -- exits FIRST (stop detection before tasks finish)

This ordering is a hard constraint. Getting it wrong causes ClosedResourceError during shutdown. Place new services carefully in this sequence.

## ProcessStarter Strategy Pattern

Each execution mode has a ProcessStarter implementation. To add a new execution mode, implement the ProcessStarter protocol and inject it into FlowRunExecutor -- do not add a new code path to Runner.

## Storage Base Path Scoping

`$STORAGE_BASE_PATH` in `deployment.path` comes from `RunnerDeployment.from_storage()`. For work-pool deployments, `path` is set to `None` on create and storage is serialized into `pull_steps` instead (`deployments/runner.py:407-413`). `load_flow_from_flow_run()` only does `$STORAGE_BASE_PATH` substitution when `pull_steps` is absent (`flows.py:3084`). So the CLI `prefect flow-run execute` path (worker-based, always has `pull_steps`) does not need `tmp_dir` / `PREFECT__STORAGE_BASE_PATH`. Only Runner-served deployments (no work pool) use this substitution.

## State Transition Split (ScheduledRunPoller vs FlowRunExecutor)

`ScheduledRunPoller` now calls `propose_pending` (Scheduled → Pending) before handing off to `FlowRunExecutor`. `FlowRunExecutor` then calls `propose_submitting` (Pending → Submitting sub-state) as step 1 of its lifecycle **when `propose_submitting=True` (the default)**. These are two separate transitions — do not collapse them. The split exists so automations listening for the Pending state fire correctly before the executor begins.

**Exception: `prefect flow-run execute` CLI path sets `propose_submitting=False`** via `FlowRunExecutorContext.create_executor(propose_submitting=False)`. The CLI is invoked by a worker that has already advanced the flow run past the Pending state, so proposing Submitting again would be wrong. The cancelling precheck (step 1a) still runs unconditionally even when `propose_submitting=False`.

## ProcessWorker Migration (Known Gap)

ProcessWorker (src/prefect/workers/process.py) calls `Runner.execute_flow_run()` and `Runner.execute_bundle()` via the deprecated path, suppressing `PrefectDeprecationWarning` with `warnings.catch_warnings()`. It bypasses FlowRunExecutor, ProcessManager, and ProcessStarter entirely. This is a known migration target.

## GitRepository Input Validation

`GitRepository.__init__` (storage.py) enforces two non-obvious constraints:

- **`commit_sha`** must match `^[0-9a-fA-F]{4,64}$` — any value that fails (including git option strings like `--upload-pack=...`) raises `ValueError`. Branch/tag names must use the `branch` parameter instead.
- **`directories`** entries starting with `--` trigger a `UserWarning` but are not rejected. The values are passed to `git sparse-checkout set --` (with a `--` separator to prevent flag injection). The warning exists because such paths are unusual; legitimate use is allowed.

These validations exist to prevent git argument injection. Do not bypass them when constructing `GitRepository` programmatically.

## Reference

Full refactor design and rationale: plans/completed/2026-02-18-runner-refactor.md
