# Runner

Thin facade over single-responsibility extracted classes. New behavior belongs in the extracted classes, not the Runner.

## Architecture

`Runner` (runner.py) delegates to these classes:

| Class | File | Responsibility |
|---|---|---|
| FlowRunExecutor | _flow_run_executor.py | Per-run lifecycle: pending -> start -> wait -> crashed/hooks |
| ProcessManager | _process_manager.py | Process map, PID tracking, kill with SIGTERM->SIGKILL |
| StateProposer | _state_proposer.py | All API state transition proposals |
| CancellationManager | _cancellation_manager.py | Kill -> hooks -> state -> event cancellation sequence |
| HookRunner | _hook_runner.py | on_cancellation / on_crashed hook execution |
| EventEmitter | _event_emitter.py | Event emission via EventsClient |
| LimitManager | _limit_manager.py | Concurrency limiting |
| DeploymentRegistry | _deployment_registry.py | Deployment/flow/storage/bundle maps |
| ScheduledRunPoller | _scheduled_run_poller.py | Poll loop, run discovery, scheduling |
| ProcessStarter (protocol) | _flow_run_executor.py | Strategy interface for starting processes |
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
- `execute_bundle()`'s inline lifecycle -- should use FlowRunExecutor with BundleExecutionStarter

These will be removed once internal callers (notably ProcessWorker) are migrated.

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

## ProcessWorker Migration (Known Gap)

ProcessWorker (src/prefect/workers/process.py) calls `Runner.execute_flow_run()`, which uses the legacy `_submit_run_and_capture_errors` -> `_run_process` path. It bypasses FlowRunExecutor, ProcessManager, and ProcessStarter entirely. This is a known migration target.

## Reference

Full refactor design and rationale: plans/completed/2026-02-18-runner-refactor.md
