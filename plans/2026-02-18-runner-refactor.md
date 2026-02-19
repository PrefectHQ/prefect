# Runner Refactor

## Goal

Decompose the 1757-line monolithic `Runner` class (`src/prefect/runner/runner.py`) into two **mode classes** — one per distinct operation mode — backed by a layer of shared services, with `Runner` itself becoming a thin backward-compatible facade. Internal architecture becomes modular and independently testable; no public API changes.

## Non-Goals

1. Changing Runner's public API — all current method signatures and behavior preserved exactly
2. Refactoring `storage.py` or `server.py` — already well-separated, out of scope
3. Adding new features, changing behavior, or optimizing performance
4. Introducing public service classes — all extracted classes are `_`-prefixed internal
5. Facade removal — planned as follow-up work: (a) migrate internal usages to compose services directly, then (b) deprecate the `Runner` facade for eventual public removal

## Background

### Current State

`src/prefect/runner/runner.py` is 1757 lines handling three conceptually distinct operations tangled together in one class:

1. **Polling mode** (`start()`): Polls for scheduled runs, submits them via `_get_and_submit_flow_runs`, manages the polling loop and webserver lifecycle
2. **Single-run mode** (`execute_flow_run()`): Executes a single flow run by ID, either as a direct subprocess (`run_flow_in_subprocess`) or via `python -m prefect.engine`
3. **Bundle mode** (`execute_bundle()`): Executes a serialized bundle in a `multiprocessing.SpawnProcess`

These modes share infrastructure — process tracking (`_flow_run_process_map`), concurrency limiting (`_limiter`), cancellation handling (`_cancelling_observer`), state proposals, hook execution, event emission — all tangled together in one class.

The package today is flat:

```
src/prefect/runner/
├── __init__.py      (re-exports Runner only)
├── runner.py        (1757 lines — the target)
├── server.py        (webserver — stays untouched)
└── storage.py       (storage backends — stays untouched)
```

The test suite is `tests/runner/test_runner.py` — 4185 lines, 154 test functions. It must pass without modification throughout every phase.

### Problem

The monolith is hard to test in isolation (every unit test boots the full Runner), hard to reason about (three execution modes share state), and hard to extend safely (a regression in process tracking can silently break hook execution or event emission).

## Target Architecture

The refactor is organized around two central ideas: **mode classes** that own each distinct operation, and **shared services** that the mode classes compose.

### Mode Classes

The three Runner operations map to two mode classes:

| Runner Operation | Public Method | Mode Class | Notes |
|---|---|---|---|
| Polling mode | `start()` | `_ScheduledRunPoller` | Owns poll loop, run discovery, and scheduling |
| Single-run mode | `execute_flow_run()` | `_FlowRunExecutor` | Owns the full flow run lifecycle |
| Bundle mode | `execute_bundle()` | `_FlowRunExecutor` | Same lifecycle, different process starter |

Bundle and single-run share the same lifecycle — only the process-starting step differs. Tracing through the current code makes this concrete:

```
                        execute_flow_run()          execute_bundle()
                        ──────────────────          ────────────────
acquire slot            _acquire_limit_slot()       _acquire_limit_slot()
read flow run           _client.read_flow_run()     FlowRun.model_validate(bundle)
check if cancelling     is_cancelling()? → mark_cancelled + release slot + return
check if cancelled      is_cancelled()? → release slot + return
start process           _run_process()            ← execute_bundle_in_subprocess()
add to process map      _add_flow_run_process_map_entry()
wait for exit           (via task group)             anyio.to_thread.run_sync(process.join)
remove from map         _remove_flow_run_process_map_entry()
interpret exit code     (duplicated switch on exit code)
propose crashed         _propose_crashed_state()    _propose_crashed_state()
run hooks               _run_on_crashed_hooks()     _run_on_crashed_hooks()
release slot            _release_limit_slot()       _release_limit_slot()
```

`_FlowRunExecutor` owns this shared lifecycle. The one differing step is expressed as a `ProcessStarter` strategy injected per call:

```python
# execute_flow_run() — facade picks starter based on whether the flow is in the deployment map
starter = _DirectSubprocessStarter(flow) if flow else _EngineSubprocessStarter()
await self._executor.submit(flow_run, starter, entrypoint=entrypoint, ...)

# execute_bundle() — bundle starter has the bundle baked in at construction
starter = _BundleSubprocessStarter(bundle=bundle, cwd=cwd, env=env)
await self._executor.submit(flow_run, starter)
```

`_ScheduledRunPoller` is genuinely different: it owns a long-running poll loop, discovers scheduled runs via the API, and delegates individual run submission to `_FlowRunExecutor`. It never shares its polling state with the executor.

### Shared Services

Mode classes don't implement cross-cutting concerns themselves — they compose these services:

- **_ProcessManager**: process map, PID tracking, async kill with SIGTERM/SIGKILL grace period
- **_LimitManager**: concurrency limiting (wraps `anyio.CapacityLimiter`)
- **_StateProposer**: all Prefect API state transition proposals
- **_HookRunner**: on_cancellation / on_crashed hook execution
- **_EventEmitter**: event emission via EventsClient
- **_CancellationManager**: kill → hooks → state → event cancellation sequence
- **_DeploymentRegistry**: deployment/flow/storage/bundle maps

### Structure Diagram

**Before** — one 1757-line class handling everything:

```
┌─────────────────────────────────────────────────────────┐
│                      Runner                             │
│                                                         │
│  polling loop · process tracking · state proposals      │
│  cancellation · hooks · events · concurrency limiting   │
│  single-run execution · bundle execution · webserver    │
└─────────────────────────────────────────────────────────┘
```

**After** — the poller delegates to the executor, which composes the shared services:

```
        ┌────────────────────────────────────────────────────────────┐
        │                     Runner  (facade)                       │
        │      start()    execute_flow_run()    execute_bundle()     │
        └───────────────┬───────────────────────────┬────────────────┘
                        │                           │
         ┌──────────────▼──────────────┐            │
         │     _ScheduledRunPoller     │            │
         │                             │            │
         │  · poll loop                │            │
         │  · run discovery            │            │
         │  · scheduling & dedup       │            │
         └──────────────┬──────────────┘            │
                        │ delegates                 │
                        ▼                           │
         ┌──────────────────────────────────────────▼──────────────┐
         │                   _FlowRunExecutor                      │
         │                                                         │
         │  ProcessStarter (injected per call):                    │
         │  · _DirectSubprocessStarter  (SpawnProcess)             │
         │  · _EngineSubprocessStarter  (anyio.Process)            │
         │  · _BundleSubprocessStarter  (SpawnProcess)             │
         └──────────────────────────┬──────────────────────────────┘
                                    │ composes
         ┌──────────────────────────▼─────────────────────────────────┐
         │                    Shared Services                         │
         │                                                            │
         │  _ProcessManager    _LimitManager      _StateProposer      │
         │  _HookRunner        _EventEmitter      _DeploymentRegistry │
         │  _CancellationManager                                      │
         └────────────────────────────────────────────────────────────┘
```

`_ScheduledRunPoller` delegates all execution to `_FlowRunExecutor` and has no direct relationship with most shared services. Its only narrow direct dependencies are `_LimitManager` (a read-only `has_slots_available()` check to decide whether to break the submission loop) and the Prefect API client (to query scheduled runs). Everything else — state proposals, process tracking, hooks, events — flows through the executor.

`_CancellationManager` is a shared service rather than a mode class — it is triggered reactively by `FlowRunCancellingObserver` callbacks, not driven by a mode's entry point.

### AsyncExitStack Initialization Order

This order is a hard constraint — teardown is LIFO, and getting this wrong causes `ClosedResourceError` during shutdown (see P1):

```
1. client          (facade owns; services receive reference, never ownership)
2. process_manager (alive for full runner lifetime)
3. limit_manager   (alive for full runner lifetime)
4. event_emitter   (owns EventsClient; must outlive services that emit events)
5. runs_task_group (cancellation callbacks schedule tasks into it)
6. cancellation_manager  (exits first: stops observer before tasks finish)
```

LIFO teardown: `cancellation_manager → runs_task_group → event_emitter → limit_manager → process_manager → client`

## Implementation Phases

### Phase 1: Leaf Services

Extract foundation services with zero dependencies on other extracted services. These form the base layer all subsequent services compose from.

**Deliverables**: `_process_manager.py`, `_limit_manager.py`

```python
# src/prefect/runner/_process_manager.py

class _ProcessManager:
    def __init__(
        self,
        *,
        on_process_added: Callable[[UUID], None] | None = None,
        on_process_removed: Callable[[UUID], None] | None = None,
    ) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...

    async def add(self, flow_run_id: UUID, entry: ProcessMapEntry) -> None: ...
    async def remove(self, flow_run_id: UUID) -> None: ...
    async def kill(self, pid: int, grace_seconds: int = 30) -> None: ...

    # Intentionally lockless — safe under single-threaded event loop + CPython dict atomicity
    def get(self, flow_run_id: UUID) -> ProcessMapEntry | None: ...
    def snapshot(self) -> list[tuple[UUID, ProcessMapEntry]]: ...  # for sync iteration (signal handler)
```

```python
# src/prefect/runner/_limit_manager.py

class _LimitManager:
    def __init__(self, *, limit: int | None) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...

    def acquire_nowait(self, flow_run_id: UUID) -> bool: ...  # False = no slot available
    def release(self, flow_run_id: UUID) -> None: ...
    def has_slots_available(self) -> bool: ...  # limit=None → returns False (preserves current behavior; no CapacityLimiter means capacity unknown)

    @property
    def borrowed_tokens(self) -> int: ...
```

**Key design decisions**:

- `_ProcessManager` fires `on_process_added`/`on_process_removed` callbacks to notify the `FlowRunCancellingObserver` without direct coupling — the facade provides these at construction time (P6 mitigation)
- Lockless reads on the process map are **intentional and correct**: async code runs on a single event loop thread, and CPython dict reads are atomic. The async lock only protects add/remove to prevent check-then-act races. Never add `threading.Lock` (P4)
- `snapshot()` returns `list(dict.items())` — iteration-safe copy for sync context (signal handler cannot hold async lock) (P2 mitigation)
- `_LimitManager` is the sole owner of acquire/release — no other service touches the `CapacityLimiter` directly. The borrower identity is the `UUID` object threaded through the lifecycle; never reconstruct from string (P3)

**Status**:
- [ ] `src/prefect/runner/_process_manager.py`
- [ ] `src/prefect/runner/_limit_manager.py`
- [ ] `tests/runner/test_process_manager.py`
- [ ] `tests/runner/test_limit_manager.py`
- [ ] All 154 existing Runner tests pass (zero regressions)

---

### Phase 2: API-Facing Services

Extract services that interact with external APIs (Prefect API, Events API). These receive the client as a constructor argument — they never own client lifecycle.

**Deliverables**: `_state_proposer.py`, `_hook_runner.py`, `_event_emitter.py`

```python
# src/prefect/runner/_state_proposer.py

class _StateProposer:
    """Stateless — no __aenter__/__aexit__ needed."""

    def __init__(self, *, client: PrefectClient) -> None: ...

    async def propose_pending(self, flow_run: FlowRun) -> bool: ...
    async def propose_failed(self, flow_run: FlowRun, exc: Exception) -> None: ...
    async def propose_crashed(self, flow_run: FlowRun, message: str) -> State | None: ...
    async def mark_cancelled(
        self, flow_run: FlowRun, state_updates: dict[str, Any] | None = None
    ) -> None: ...

    # Sync path for SIGTERM handler — creates its own sync client internally
    def propose_awaiting_retry_sync(self, flow_run: FlowRun) -> None: ...
```

```python
# src/prefect/runner/_hook_runner.py

FlowResolver = Callable[[FlowRun], Awaitable["Flow | None"]]

class _HookRunner:
    """Stateless — no __aenter__/__aexit__ needed."""

    def __init__(self, *, resolve_flow: FlowResolver) -> None: ...

    async def run_cancellation_hooks(self, flow_run: FlowRun, state: State) -> None: ...
    async def run_crashed_hooks(self, flow_run: FlowRun, state: State) -> None: ...
```

```python
# src/prefect/runner/_event_emitter.py

class _EventEmitter:
    def __init__(self, *, runner_name: str) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...

    async def emit_flow_run_cancelled(
        self,
        flow_run: "FlowRun",
        flow: "APIFlow | None",
        deployment: "DeploymentResponse | None",
    ) -> None: ...
    # flow and deployment supply related resources + tags for the event payload;
    # callers resolve these before calling (CancellationManager fetches them from the API)
```

**Key design decisions**:

- `_HookRunner` receives a `FlowResolver` callback rather than direct map references. The facade provides this callback, closing over `_deployment_registry` and `_tmp_dir`. This keeps HookRunner testable with a simple lambda and breaks the tight coupling that would require 4-5 constructor args (P13)
- `_StateProposer.propose_awaiting_retry_sync()` creates its own sync client — it does **not** use the async `client` passed at construction, because it runs from a signal handler on an arbitrary thread (P2)
- `_EventEmitter` owns the `EventsClient` lifecycle (entered into Runner's exit stack at position 4 in the dependency order)
- Services never enter `self._client` into their own exit stacks — only the facade manages client lifecycle (P14)

**Status**:
- [ ] `src/prefect/runner/_state_proposer.py`
- [ ] `src/prefect/runner/_hook_runner.py`
- [ ] `src/prefect/runner/_event_emitter.py`
- [ ] `tests/runner/test_state_proposer.py`
- [ ] `tests/runner/test_hook_runner.py`
- [ ] `tests/runner/test_event_emitter.py`
- [ ] All 154 existing Runner tests pass

---

### Phase 3: Execution Mode Class & Supporting Services

Extract `_FlowRunExecutor` — the mode class for `execute_flow_run()` and `execute_bundle()` — along with the supporting services it composes.

**Deliverables**: `_execution.py`, `_cancellation_manager.py`, `_deployment_registry.py`

```python
# src/prefect/runner/_execution.py

class ProcessHandle(Protocol):
    """Normalizes anyio.abc.Process and multiprocessing.SpawnProcess."""
    @property
    def pid(self) -> int: ...
    async def wait(self) -> int: ...  # returns exit code

class ProcessStarter(Protocol):
    """Pluggable strategy for starting a flow run process."""
    async def start(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[ProcessHandle],
        *,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: "Path | str | None" = None,
        env: "dict[str, str | None] | None" = None,
        stream_output: bool = True,
    ) -> None: ...  # signals ProcessHandle early via task_status.started(handle), then blocks until exit

def interpret_exit_code(exit_code: int | None) -> tuple[int, str | None]:
    """Returns (log_level, help_message) for a given exit code. Shared by all strategies."""
    ...

class _FlowRunExecutor:
    def __init__(
        self,
        *,
        process_manager: _ProcessManager,
        limit_manager: _LimitManager,
        state_proposer: _StateProposer,
        hook_runner: _HookRunner,
        runs_task_group: anyio.abc.TaskGroup,
    ) -> None: ...

    async def submit(
        self,
        flow_run: "FlowRun",
        starter: ProcessStarter,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
        *,
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: "Path | str | None" = None,
        env: "dict[str, str | None] | None" = None,
        stream_output: bool = True,
    ) -> None: ...  # signals ProcessHandle via task_status when process starts; runs full lifecycle
```

```python
# src/prefect/runner/_cancellation_manager.py

class _CancellationManager:
    def __init__(
        self,
        *,
        process_manager: _ProcessManager,
        state_proposer: _StateProposer,
        hook_runner: _HookRunner,
        event_emitter: _EventEmitter,
        client: "PrefectClient",
        # Facade provides this — a bound method that schedules cancellation
        # in runs_task_group if the group is still active
        cancel_dispatch: Callable[[UUID], None],
        polling_interval: float,
    ) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...

    async def cancel_run(
        self, flow_run: "FlowRun | UUID", state_msg: str | None = None
    ) -> None: ...
    async def cancel_all(self) -> None: ...
    async def handle_observer_failure(self) -> None: ...
```

```python
# src/prefect/runner/_deployment_registry.py

class _DeploymentRegistry:
    """No lifecycle needed — holds flow/storage/bundle maps."""

    def register_deployment(
        self,
        deployment_id: UUID,
        *,
        flow: "Flow | None" = None,
        storage: "RunnerStorage | None" = None,
    ) -> None: ...

    def get_flow(self, deployment_id: UUID) -> "Flow | None": ...
    def get_storage(self, deployment_id: UUID) -> "RunnerStorage | None": ...

    def set_bundle(self, flow_run_id: UUID, bundle: "SerializedBundle") -> None: ...
    def get_bundle(self, flow_run_id: UUID) -> "SerializedBundle | None": ...
    def clear_bundle(self, flow_run_id: UUID) -> None: ...

    async def resolve_flow(self, flow_run: "FlowRun") -> "Flow | None":
        """Resolution order: bundle map → deployment flow map → API entrypoint."""
        ...
```

**Key design decisions**:

- `interpret_exit_code` is a module-level function — it eliminates the exit-code switch duplicated at lines 1375–1411 (flow run path) and 794–830 (bundle path) in the current monolith (P5)
- `_FlowRunExecutor.submit` has a single `try/finally` that releases the limit slot exactly once. The dual-release paths currently at lines 697/702 (execute_flow_run early exit) and 1431 (submit_run_and_capture_errors finally) are collapsed into this one path (P3)
- `_CancellationManager` receives `cancel_dispatch` from the facade — a bound method that checks task group liveness before scheduling a cancel task. Never a raw lambda closing over `self._runs_task_group` (P6)
- `_DeploymentRegistry` consolidates `_deployment_flow_map`, `_flow_run_bundle_map`, `_deployment_storage_map`, `_deployment_cache`, `_flow_cache`, and `_deployment_ids` — all currently scattered on Runner

**Status**:
- [ ] `src/prefect/runner/_execution.py` (`ProcessHandle`, `ProcessStarter`, `interpret_exit_code`, `_FlowRunExecutor`, three starter implementations)
- [ ] `src/prefect/runner/_cancellation_manager.py`
- [ ] `src/prefect/runner/_deployment_registry.py`
- [ ] `tests/runner/test_execution.py`
- [ ] `tests/runner/test_cancellation_manager.py`
- [ ] All 154 existing Runner tests pass

---

### Phase 4: Scheduled Run Poller Mode Class

Extract `_ScheduledRunPoller` — the mode class for `start()`. With this phase complete, both mode classes exist and the Runner's three operations each have a clear home.

**Deliverables**: `_scheduled_run_poller.py`

```python
# src/prefect/runner/_scheduled_run_poller.py

class _ScheduledRunPoller:
    def __init__(
        self,
        *,
        executor: _FlowRunExecutor,
        limit_manager: _LimitManager,
        client: "PrefectClient",
        deployment_ids: set[UUID],
        query_seconds: float,
        prefetch_seconds: float,
        resolve_starter: "Callable[[FlowRun], ProcessStarter]",
        storage_objs: "list[RunnerStorage]",
    ) -> None: ...

    # Blocks until stop() cancels the scope. Does NOT use __aenter__/__aexit__.
    # run() starts one loop per storage (pull_code) + the scheduling loop inside _loops_task_group.
    async def run(self, run_once: bool = False) -> None: ...
    async def stop(self) -> None: ...

    @property
    def last_polled(self) -> "datetime.datetime | None": ...
```

**Key design decisions**:

- `_ScheduledRunPoller` has no `__aenter__`/`__aexit__`. It creates `_loops_task_group` internally and uses it as a blocking `async with` inside `run()`. Entering it into any exit stack would break the blocking semantics (P11)
- `_submitting_flow_run_ids` lives in `_ScheduledRunPoller` only — it is irrelevant to `execute_flow_run` (single-run mode) and should not be shared (P10)
- `stop()` cancels the `_loops_task_group` scope; the facade's `astop()` calls `_scheduled_run_poller.stop()` — the facade never touches `_loops_task_group` directly
- Storage pulls run inside `_loops_task_group` alongside the scheduling loop: `run()` starts a `critical_service_loop(storage.pull_code, interval=storage.pull_interval)` per storage with `pull_interval`, or a one-shot `storage.pull_code` for those without. Tests assert pull behavior via Runner, so this must be preserved exactly (runner.py:587–608)
- `resolve_starter` is a facade-provided factory called per scheduled run: `lambda flow_run: _DirectSubprocessStarter(registry.get_flow(flow_run.deployment_id)) if registry.get_flow(...) else _EngineSubprocessStarter()`. This keeps starter construction in one place and correctly handles multiple deployments with distinct flows

**Status**:
- [ ] `src/prefect/runner/_scheduled_run_poller.py`
- [ ] `tests/runner/test_scheduled_run_poller.py`
- [ ] All 154 existing Runner tests pass

---

### Phase 5: Facade Wiring

Wire all services into `Runner`. `runner.py` shrinks from 1757 lines to ~400–500 lines.

**Deliverables**: Final `runner.py`

The facade's `__aenter__` wires services in explicit dependency order:

```python
async def __aenter__(self) -> Self:
    # Must capture loop before any service initialization (P12)
    self._loop = asyncio.get_event_loop()

    self._client = get_client()
    await self._exit_stack.enter_async_context(self._client)          # 1
    await self._exit_stack.enter_async_context(self._process_manager) # 2
    await self._exit_stack.enter_async_context(self._limit_manager)   # 3
    await self._exit_stack.enter_async_context(self._event_emitter)   # 4
    await self._exit_stack.enter_async_context(self._runs_task_group) # 5
    await self._exit_stack.enter_async_context(                       # 6
        self._cancellation_manager
    )
    self.started = True
    return self

async def __aexit__(self, *exc_info: Any) -> None:
    if self.pause_on_shutdown:
        await self._pause_schedules()      # ← must fire before exit stack unwinds (line 1709)
    self.started = False
    for scope in self._scheduled_task_scopes:
        scope.cancel()
    await self._exit_stack.__aexit__(*exc_info)
    shutil.rmtree(str(self._tmp_dir), ignore_errors=True)
    del self._runs_task_group, self._loops_task_group
```

`_pause_schedules` pauses all registered deployment schedules via `self._client` and `self._deployment_ids`. It stays on the facade — it composes `_client` (facade-owned) with `_deployment_ids` from `_deployment_registry`. This behavior is asserted by test line 718.

The public methods on the facade — signatures unchanged:

```python
class Runner:
    async def start(self, run_once: bool = False, webserver: bool | None = None) -> None: ...
    async def astop(self) -> None: ...
    @async_dispatch(astop)
    def stop(self) -> None: ...

    async def aadd_flow(self, flow: "Flow[Any, Any]", ...) -> UUID: ...
    @async_dispatch(aadd_flow)
    def add_flow(self, flow: "Flow[Any, Any]", ...) -> UUID: ...

    async def aadd_deployment(self, deployment: "RunnerDeployment") -> UUID: ...
    @async_dispatch(aadd_deployment)
    def add_deployment(self, deployment: "RunnerDeployment") -> UUID: ...

    async def execute_flow_run(self, flow_run_id: UUID, ...) -> "anyio.abc.Process | SpawnProcess | None": ...
    async def execute_bundle(self, bundle: "SerializedBundle", ...) -> None: ...
    def execute_in_background(self, func: Callable, *args: Any, **kwargs: Any) -> "Future[Any]": ...
    async def cancel_all(self) -> None: ...
    def has_slots_available(self) -> bool: ...
    def reschedule_current_flow_runs(self) -> None: ...  # sync — uses snapshot(), sync client
    def handle_sigterm(self, *args: Any, **kwargs: Any) -> None: ...

    # Facade properties for server.py compatibility
    @property
    def _flow_run_process_map(self) -> "dict[UUID, ProcessMapEntry]": ...
    # ⚠ Must return the LIVE mutable dict owned by _process_manager — not a copy or snapshot.
    # Tests mutate it directly (runner._flow_run_process_map[id] = {...}) before calling
    # methods that read from it (lines 3854, 3887). A copied snapshot breaks those tests.
    @property
    def last_polled(self) -> "datetime.datetime | None": ...  # → _scheduled_run_poller.last_polled
    @last_polled.setter
    def last_polled(self, value: "datetime.datetime | None") -> None: ...  # tests assign directly (lines 2983, 2988)

    # ── Internal attributes — tests access these directly ────────────────────────
    # These must be real runtime properties (with getter + setter) or actual instance
    # attributes — NOT bare class-level annotations. Bare annotations create no runtime
    # attribute and raise AttributeError when accessed or assigned.
    #
    @property
    def _client(self) -> "PrefectClient": ...      # owned by facade; tests monkeypatch methods on it (e.g. line 1638)
    @property
    def _limiter(self) -> "anyio.CapacityLimiter | None": ...  # → _limit_manager; None when limit=None (line 291)
    @property
    def _storage_objs(self) -> "list[RunnerStorage]": ...      # → _deployment_registry (line 1317)
    @property
    def _tmp_dir(self) -> "Path": ...              # owned by facade; tests pre-create it (line 1564)
    @property
    def _cancelling_flow_run_ids(self) -> "set[UUID]": ...     # → _cancellation_manager's actual set (line 1356); returns the live set so .add() propagates

    # ── Private method passthroughs ──────────────────────────────────────────────
    # Tests call these private methods directly on runner instances.
    # The facade preserves them as one-liner forwarding methods — do NOT remove.
    #
    def _acquire_limit_slot(self, flow_run_id: "UUID") -> bool: ...              # sync, returns True when no limiter (unlimited) — → _limit_manager.acquire_nowait()
    def _release_limit_slot(self, flow_run_id: "UUID") -> None: ...              # → _limit_manager.release()
    async def _run_on_crashed_hooks(self, flow_run: "FlowRun", state: "State") -> None: ...
    async def _run_on_cancellation_hooks(self, flow_run: "FlowRun", state: "State") -> None: ...
    # ⚠ NOT pure passthroughs — tests patch "prefect.runner.runner.load_flow_from_flow_run"
    # AFTER runner construction (line 1127) then call these methods on an unstarted runner
    # (no async with runner:, so _hook_runner is never constructed). The methods must stay
    # as real implementations on the facade, calling module-level load_flow_from_flow_run
    # and _run_hooks by name so the runtime patch is in effect at call time.
    async def _run_process(self, *args: Any, **kwargs: Any) -> "int | None": ... # returns exit code (not process!) — forwards to starter implementation
    async def _kill_process(self, pid: int, grace_seconds: int = 30) -> None: ... # → _process_manager.kill()
    def _get_flow_run_logger(self, flow_run: "FlowRun") -> "logging.Logger": ... # creates per-run logger; stays on facade
    async def _get_and_submit_flow_runs(self) -> None: ...                       # → _scheduled_run_poller._get_and_submit()
    async def _cancel_run(self, flow_run: "FlowRun | UUID", state_msg: "str | None" = None) -> None: ...  # → _cancellation_manager.cancel_run()
    async def _propose_crashed_state(self, flow_run: "FlowRun", msg: str) -> None: ...  # → _state_proposer.propose_crashed()
    async def _mark_flow_run_as_cancelled(self, flow_run: "FlowRun", state_updates: "dict[str, Any] | None" = None) -> None: ...  # → _state_proposer.mark_cancelled()
    async def _handle_cancellation_observer_failure(self) -> None: ...
    # ⚠ NOT a pure passthrough — tests patch.object(runner, "_kill_process") and
    # patch.object(runner, "_get_flow_run_logger") then call this method and assert those
    # patched versions were invoked (lines 3862, 3865, 3894). The facade implementation
    # must call self._kill_process() and self._get_flow_run_logger() directly so
    # patch.object interception works. Delegating to _cancellation_manager.handle_observer_failure()
    # would bypass the facade's patched attributes and silently break these tests.
```

Preserved re-exports for test monkeypatching (see P9):
```python
# runner.py — at module level, preserved for test monkeypatching
# Tests patch these names at prefect.runner.runner.<name> — they must live here after the move
import threading as threading                                                       # noqa: F401
# ^ mocker.patch("prefect.runner.runner.threading.Thread", ...) — line ~2995
from prefect.runner._execution import run_process as run_process                   # noqa: F401
# ^ mocker.patch("prefect.runner.runner.run_process", ...) — lines ~201, 1215, 1256, 1513
from prefect.events.clients import get_events_client as get_events_client           # noqa: F401
# ^ mocker.patch("prefect.runner.runner.get_events_client", ...) — line ~212
from prefect.utilities.engine import propose_state as propose_state                # noqa: F401
# ^ mocker.patch("prefect.runner.runner.propose_state", ...) — line ~1604
from prefect.flows import load_flow_from_flow_run as load_flow_from_flow_run       # noqa: F401
# ^ patch("prefect.runner.runner.load_flow_from_flow_run", ...) — line ~1127
#   _run_on_cancellation_hooks/_run_on_crashed_hooks call this by module-level name
from prefect.runner._hook_runner import _run_hooks as _run_hooks                   # noqa: F401
# ^ from prefect.runner.runner import _run_hooks — line 2036
#   _run_hooks moves to _hook_runner.py but stays importable from runner.py
```

**Key constraints**:
- All `@async_dispatch` decorators stay on the `Runner` facade — never move them to service classes. The dispatch chain is always: `sync_method → async_dispatch → facade_async_method → service_method` (P7)
- `execute_flow_run` and `execute_bundle` conditional self-context re-entrance stays on the facade: `context = self if not self.started else asyncnullcontext()` (P8)
- `execute_in_background` and `_loop` stay on the facade — this bridges the sync webserver thread to the async runner loop (P12)
- `reschedule_current_flow_runs` stays sync on the facade, calls `_process_manager.snapshot()` for lockless reads and `_state_proposer.propose_awaiting_retry_sync()` (P2)
- Services must receive patchable callables (`run_process`, `propose_state`, `get_events_client`) as **constructor arguments injected by the facade** — never imported directly inside service modules. When tests patch `prefect.runner.runner.run_process`, the patched reference is the one the facade holds and has already passed in. Re-exports alone are insufficient if services import from source modules directly at call time.
- `execute_flow_run()` returns `anyio.abc.Process | SpawnProcess | None` (existing public contract). Since `submit()` returns `None`, the facade retrieves the `ProcessHandle` early via the anyio task_status protocol: `handle = await self._runs_task_group.start(self._executor.submit, flow_run, starter, ...)`. The facade then returns `handle.raw_process`. `_run_process` returns `int | None` (exit code) — the `_run_process` passthrough must match this, not `anyio.abc.Process`.
- `_run_on_cancellation_hooks` and `_run_on_crashed_hooks` are **not pure passthroughs to `_HookRunner`** — tests patch `prefect.runner.runner.load_flow_from_flow_run` after runner construction and call these methods on an unstarted runner (no `async with runner:`, so `_hook_runner` is never constructed). The facade must implement these methods inline, calling module-level `load_flow_from_flow_run` and `_run_hooks` by name so the runtime patch is in effect. `_run_hooks` moves to `_hook_runner.py` but is re-exported from `runner.py`; `load_flow_from_flow_run` is also re-exported at module level (line 2036 imports from `prefect.runner.runner`).
- `_handle_cancellation_observer_failure` is **not a one-liner passthrough** — it must stay on the facade as a real method body calling `self._kill_process()` and `self._get_flow_run_logger()`, because tests use `patch.object(runner, "_kill_process")` and `patch.object(runner, "_get_flow_run_logger")` and then call this method, asserting the patched versions were invoked. A pure delegation to `_cancellation_manager.handle_observer_failure()` would bypass those patches. When `PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE=True`, the method sets `self.stopping = True`; this flag is then checked by `_get_and_submit_flow_runs` to short-circuit polling (line 1071).
- `__aexit__` must call `await self._pause_schedules()` when `self.pause_on_shutdown` is true, before the exit stack unwinds (line 1709, tested at line 718). `_pause_schedules` stays on the facade and accesses `self._client` and `self._deployment_ids`.
- `_flow_run_process_map` must return the **live mutable dict** owned by `_process_manager` — not a copy or snapshot. Tests mutate it directly (lines 3854, 3887) before calling methods that read from it.
- Internal attributes (`_client`, `_limiter`, `_storage_objs`, `_tmp_dir`, `_cancelling_flow_run_ids`) must be real runtime properties or instance attributes — not bare class-level annotations. Tests assign to `last_polled` directly (lines 2983/2988), so the `last_polled` property requires both a getter and a setter.

**Status**:
- [ ] `runner.py` reduced to ~400–500 lines
- [ ] All 154 existing Runner tests pass without modification
- [ ] `_flow_run_process_map` and `last_polled` accessible via facade properties
- [ ] `@async_dispatch` stays on facade only
- [ ] Self-context re-entrance in `execute_flow_run`/`execute_bundle` preserved
- [ ] `reschedule_current_flow_runs` and `handle_sigterm` work from sync context
- [ ] Re-exports preserved for test monkeypatching

---

## Known Pitfalls

These are the non-obvious traps identified in pre-refactor research.

| Pitfall | Severity | Where It Bites | Mitigation Summary |
|---------|----------|----------------|-------------------|
| **P1** AsyncExitStack teardown order | Critical | Phase 5 | Hard-coded entry order; `cancellation_manager → runs_task_group → event_emitter → limit_manager → process_manager → client` |
| **P2** Signal handler sync/async boundary | Critical | Phase 2, 5 | `reschedule_current_flow_runs` uses `snapshot()` + sync client; `StateProposer` has dedicated sync path |
| **P3** CapacityLimiter borrower identity | High | Phase 1, 3 | `_LimitManager` is sole owner; `_FlowRunExecutor` has one `try/finally` release path |
| **P4** Process map lock inconsistency | High | Phase 1 | Lockless reads are intentional; document CPython GIL guarantee; never add `threading.Lock` |
| **P5** Two process types (SpawnProcess vs Process) | High | Phase 3 | `ProcessHandle` protocol normalizes both; `interpret_exit_code` shared utility |
| **P6** Cancellation observer lambda closures | High | Phase 3, 5 | Observer receives `cancel_dispatch` bound method from facade, not raw closure over task group |
| **P7** `async_dispatch` delegation chain breaking | High | Phase 5 | All `@async_dispatch` decorators stay on `Runner` facade only |
| **P8** `execute_flow_run` self-context re-entrance | Medium-High | Phase 5 | Conditional `self if not self.started` stays on facade; executor receives pre-initialized services |
| **P9** Test monkeypatching paths | Medium-High | Phase 1–5 | `runner.py` re-exports moved names; run full test suite after every module move |
| **P10** Shared mutable state sets | Medium | Phase 1, 4 | `_submitting_flow_run_ids` in ScheduledRunPoller; `_cancelling_flow_run_ids` in CancellationManager |
| **P11** `_loops_task_group` not in exit stack | Medium | Phase 4 | ScheduledRunPoller owns loops task group inside `run()`; never in exit stack |
| **P12** `execute_in_background` loop capture | Medium | Phase 5 | `_loop` stays on facade; captured before any service init in `__aenter__` |
| **P13** Hook execution flow resolution | Medium | Phase 2 | `_HookRunner` receives `FlowResolver` callback from facade |
| **P14** Client ownership and lifecycle | Medium | Phase 1–5 | Facade owns one client; services receive reference only; exit stack order ensures client outlives all services |

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `execute_flow_run` called when runner not started | Facade enters `async with self` — initializes services, executes, tears down |
| `execute_flow_run` called while `start()` is running | Facade uses `asyncnullcontext()` — no re-initialization or double teardown |
| SIGTERM arrives while flow runs are in flight | `handle_sigterm → stop() → sys.exit(0)` — `reschedule_current_flow_runs()` is a separate public method that is NOT called by `handle_sigterm`; callers invoke it independently if they want rescheduling |
| Cancellation observer fails (websocket + polling both down) | `_handle_cancellation_observer_failure()` on facade — when `PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE=True`: sets `self.stopping = True`, logs error, kills each process via `self._kill_process()`; when disabled: logs warning via `self._get_flow_run_logger()` per run, does NOT kill or set stopping. Both branches tested at lines 3993/4010. `stopping=True` causes `_get_and_submit_flow_runs` to return early (line 1071). |
| Process exits before it is added to process map | `execute_flow_run` checks `returncode`/`exitcode` before adding to map; skips if already exited |
| Same flow run submitted twice | `_LimitManager.acquire_nowait` detects duplicate borrower and returns `False` |
| Bundle flow run cancelled | Hook resolution checks `_deployment_registry.get_bundle(flow_run.id)` first |
| Cancellation event fires after `astop()` | `cancel_dispatch` on the facade checks task group liveness; logs warning rather than crashing |

## Verification Checklist

### Automated

- [ ] `uv run pytest tests/runner/test_runner.py` — all 154 tests pass, zero modifications to test file
- [ ] `uv run pytest tests/runner/` — all service unit tests pass
- [ ] `uv run pytest tests/runner/test_runner.py -x` passes after each phase before proceeding
- [ ] `uv run mypy src/prefect/runner/` — no type errors in any new module

### Manual

- [ ] `flow.serve()` starts runner, polls for scheduled runs, submits them
- [ ] `runner.execute_flow_run(run_id)` executes standalone (runner not yet started)
- [ ] `runner.execute_bundle(bundle)` works with `SpawnProcess` lifecycle
- [ ] Cancellation via UI kills process and runs `on_cancellation` hooks
- [ ] SIGTERM to runner process stops the runner and exits cleanly (`stop()` then `sys.exit(0)`); in-flight runs are not rescheduled by the signal handler
- [ ] `runner.stop()` called from sync context terminates polling loop
- [ ] Webserver `/health` returns correct data (depends on `last_polled` facade property)
- [ ] `runner.add_flow(flow)` called from sync context creates deployment

## New File Layout

```
src/prefect/runner/
├── __init__.py                  (unchanged — exports Runner only)
├── runner.py                    (~400–500 lines: facade + re-exports)
├── _process_manager.py          (Phase 1)
├── _limit_manager.py            (Phase 1)
├── _state_proposer.py           (Phase 2)
├── _hook_runner.py              (Phase 2)
├── _event_emitter.py            (Phase 2)
├── _execution.py                (Phase 3: ProcessHandle, ProcessStarter, interpret_exit_code, _FlowRunExecutor, starters)
├── _cancellation_manager.py     (Phase 3)
├── _deployment_registry.py      (Phase 3)
├── _scheduled_run_poller.py                  (Phase 4)
├── server.py                    (unchanged)
└── storage.py                   (unchanged)
```

## References

1. Monolith target: `src/prefect/runner/runner.py`
2. Observer: `src/prefect/_observers.py` — `FlowRunCancellingObserver`
