# prefect_dbt.core

Core execution engine for the prefect-dbt integration. Contains the runner, orchestrator, manifest parser, hooks, cache, executor, and artifact logic.

## Purpose & Scope

Provides two primary execution paths for running dbt commands with Prefect:
- `PrefectDbtRunner` — wraps the dbt Python API (`dbtRunner`) for invoking CLI-style commands (`runner.invoke(["build"])`)
- `PrefectDbtOrchestrator` — wave-based execution engine that runs dbt builds with per-node or per-wave Prefect task scheduling

Does NOT interact with the dbt Cloud API (that lives in `prefect_dbt.cloud`).

## Entry Points & Contracts

- `PrefectDbtRunner` — lifecycle hooks via `DbtHookMixin`, invoke via `runner.invoke(args)`
- `PrefectDbtOrchestrator` — lifecycle hooks via `DbtHookMixin`, run via `orchestrator.run_build()`
- `DbtHookContext` — frozen dataclass passed to every hook callback; exported from `prefect_dbt` top-level
- `PrefectDbtSettings` — shared settings (project_dir, profiles_dir, target_path); consumed by both runner and orchestrator

## Lifecycle Hooks

Both `PrefectDbtRunner` and `PrefectDbtOrchestrator` inherit `DbtHookMixin` and expose three hook registration methods:

```python
@runner.on_run_start
def before(ctx: DbtHookContext): ...

@runner.post_model(select="tag:critical")
def per_model(ctx: DbtHookContext): ...

@runner.on_run_end(select="tag:marts")
def after(ctx: DbtHookContext): ...
```

Non-obvious behaviors:
- **`on_run_start` has no `select` parameter** — calling `on_run_start(select=...)` raises `TypeError`; only `on_run_end` and `post_model` accept `select`.
- **`post_model` fires only for model nodes** — tests, seeds, snapshots, and sources are silently skipped even if `select` would match them.
- **Async callbacks are supported** — the mixin detects awaitables and runs them via `run_coro_as_sync`; hooks fire synchronously regardless.
- **Hook failures never fail the build** — every exception inside a hook is caught and logged as a warning. Hooks cannot propagate errors to the caller.
- **Hooks fire outside a Prefect flow context** — for `PrefectDbtRunner`, the callback queue is created whenever `post_model` hooks are registered, even without an active flow run. Tasks are not created for nodes in that case.
- **`select` uses dbt node selection syntax** — the selection is resolved against the project manifest once per invocation and cached in `_active_hook_selection_cache`. A failed resolution (e.g., broken selector) logs a warning and treats the selector as matching nothing.

## `DbtHookContext` Fields

| Field | Available in | Notes |
|-------|-------------|-------|
| `event` | all | `"run_start"`, `"run_end"`, or `"post_model"` |
| `command` | all | dbt command string, e.g. `"build"`, `"run dbt deps"` |
| `owner` | all | the `PrefectDbtRunner` or `PrefectDbtOrchestrator` instance |
| `args` | runner only | CLI args tuple passed to `invoke()` |
| `node` | `post_model` | dbt manifest node object |
| `node_id` | `post_model` | convenience property: `node.unique_id` or `None` |
| `status` | `post_model`, `run_end` | `"success"`, `"error"`, `"skipped"`, or `None` |
| `result` | `post_model`, `run_end` | per-node result dict (runner) or node result dict (orchestrator) |
| `run_results` | `run_end` | all node results for the invocation |
| `error` | `post_model`, `run_end` (on failure) | error message in `post_model`; exception object in `run_end` |
| `node_ids` | all | all nodes in `run_start`; single-element tuple in `post_model`; all executed nodes in `run_end` |

## Pitfalls

- `_initialize_dbt_hooks()` must be called in `__init__`; both runner and orchestrator already do this. If you subclass either without calling `super().__init__()`, `_dbt_hooks` will be absent and `_has_dbt_hooks()` will raise `AttributeError`.
- The selection cache is built once before execution begins; hook selectors that reference nodes not in the resolved manifest will match nothing silently.
- `post_model` hooks in `PrefectDbtRunner` run in the background callback thread, not the main thread. Avoid thread-unsafe side effects.

## Anti-Patterns

- Don't raise exceptions in hooks to signal build failure — they are swallowed. Use `ctx.status == "error"` checks to react to failures.
- Don't use `on_run_start` to filter by model — it receives no `node`, only the full list of `node_ids`. Use `post_model` for per-model logic.
