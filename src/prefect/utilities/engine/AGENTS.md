# engine

Result-to-state linking, SIGTERM bridge management, and helpers shared by the flow/task engines.

## Purpose & Scope

Two responsibilities live here:

1. **Result-to-state linking** — glue between Python return values (which callers receive) and the `State` objects that represent them on the server. Maintains the identity-keyed `run_results` map inside `EngineContext` and exposes safe accessors.

2. **SIGTERM bridge** — installs and tears down Prefect's SIGTERM handler (`TerminationSignal`), coordinates control-intent acknowledgement with the runner, and exposes locked helpers so the engine can atomically commit cancellation intent before signalling readiness to the runner.

Naming and hook-resolution helpers for custom flow/task run names live in sibling `../_engine.py` (flat module), not here.

## Entry Points

**Result linking:**
- `link_state_to_result(state, result, run_type)` — associate a `State` with a Python object under a specific `RunType` for later lookup via `get_state_for_result`.
- `link_state_to_flow_run_result(state, result)` / `link_state_to_task_run_result(state, result)` — scoped variants used by the flow and task engines respectively.
- `get_state_for_result(obj) -> tuple[State, RunType] | None` — identity-verified lookup that handles `id()` collisions safely.

**SIGTERM bridge:**
- `capture_sigterm()` — context manager that installs Prefect's SIGTERM bridge; outermost scope installs it, nested scopes reuse or reinstall as needed. The runner's control listener connects only while this context is active.
- `is_prefect_sigterm_handler_installed() -> bool` — check (under lock) whether Prefect's bridge is the active SIGTERM handler.
- `can_ack_control_intent() -> bool` — check (under the same lock) whether the child can safely acknowledge a queued control intent.
- `commit_control_intent_and_ack(commit_intent, clear_intent, send_ack, trigger_cancel)` — atomically commit a control intent and write the ack byte to the runner, all under `_prefect_sigterm_bridge_lock`.

## Pitfalls

- **Never access `EngineContext.run_results` directly via `id(obj)`.** Always call `get_state_for_result(obj)` — the accessor verifies object identity in addition to the ID match, avoiding false hits when Python reuses an id for a different object after GC.
- **All SIGTERM-state reads and writes must hold `_prefect_sigterm_bridge_lock`.** The lock is a `threading.RLock` that serializes handler install/restore with ack writes. Reading `signal.getsignal(SIGTERM)` outside the lock creates a TOCTOU race where the handler is restored after the child decides it's safe to ack but before the runner observes the ack byte.
