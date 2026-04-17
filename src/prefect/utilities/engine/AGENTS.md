# engine

Result-to-state linking, identity-verified `EngineContext` lookups, and helpers shared by the flow/task engines.

## Purpose & Scope

This module is the glue between Python return values (which callers receive) and the `State` objects that represent them on the server. It maintains the identity-keyed `run_results` map inside `EngineContext` and exposes safe accessors for linking and retrieving those states.

Naming and hook-resolution helpers for custom flow/task run names live in sibling `../_engine.py` (flat module), not here.

## Entry Points

- `link_state_to_result(state, result, run_type)` — associate a `State` with a Python object under a specific `RunType` for later lookup via `get_state_for_result`.
- `link_state_to_flow_run_result(state, result)` / `link_state_to_task_run_result(state, result)` — scoped variants used by the flow and task engines respectively.
- `get_state_for_result(obj) -> tuple[State, RunType] | None` — identity-verified lookup that handles `id()` collisions safely.

## Pitfalls

- **Never access `EngineContext.run_results` directly via `id(obj)`.** Always call `get_state_for_result(obj)` — the accessor verifies object identity in addition to the ID match, avoiding false hits when Python reuses an id for a different object after GC.
