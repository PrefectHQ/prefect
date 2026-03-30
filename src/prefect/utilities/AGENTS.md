# Utilities

General-purpose helpers and cross-cutting tools used throughout the Prefect SDK and server.

## Purpose & Scope

Shared utilities: data manipulation, async helpers, schema tooling, callables introspection, and infrastructure helpers. These modules have no common theme beyond being broadly reused — if something is self-contained and used across two or more subsystems, it lives here.

Does NOT include: server-specific utilities (`server/utilities/`), concurrency slot management (`concurrency/`), or logging infrastructure (`logging/`).

## Key Submodules

- `schema_tools/` — Hydration and validation of `__prefect_kind` template structures (see below)
- `asyncutils.py` — Async/sync bridge utilities and concurrency helpers
- `callables.py` — Function signature introspection and parameter coercion
- `collections.py` — Extended collection helpers (visit, flatten, remove nested keys)
- `annotations.py` — Custom Prefect type annotations used in flow/task signatures
- `processutils.py` — Subprocess execution and output streaming helpers (`run_process`, `consume_process_output`, `stream_text`)
- `pydantic.py` — Pydantic v1/v2 compatibility shims
- `templating.py` — Jinja template utilities and `maybe_template()` detection

## schema_tools: Hydration System

`schema_tools/hydration.py` resolves `__prefect_kind` structures into real Python values. These structures appear in deployment parameters and automation action payloads.

### Entry Point

```python
from prefect.utilities.schema_tools.hydration import hydrate, HydrationContext

ctx = HydrationContext(render_jinja=True, jinja_context={"event": event})
result = hydrate(parameters, ctx)
```

### `__prefect_kind` Contracts

| Kind | Input structure | Output | Notes |
|------|----------------|--------|-------|
| `"jinja"` | `{"__prefect_kind": "jinja", "template": "..."}` | `str` | **Always returns a string** — even if the template renders a number |
| `"json"` | `{"__prefect_kind": "json", "value": ...}` | parsed value | If `value` is already a non-string (int, bool, list, dict, None), it is returned as-is without JSON decoding |
| `"workspace_variable"` | `{"__prefect_kind": "workspace_variable", "variable_name": "..."}` | variable value | Requires `render_workspace_variables=True` in context |

**Critical non-obvious invariant:** `jinja` kind always returns a `str`. To preserve the original type of a templated value (int, float, bool, list, dict), use the json+jinja pattern with `| tojson`:

```python
# Type-preserving round-trip for a single expression:
{
    "__prefect_kind": "json",
    "value": {
        "__prefect_kind": "jinja",
        "template": "{{ value | tojson }}"
    }
}
# Renders {{ value | tojson }} → JSON string → json.loads() → original type
```

This is the pattern used by `RunDeployment._wrap_v1_template` for single-expression Jinja parameters.

### Placeholder Protocol

Handlers return `Placeholder` subclasses (e.g. `RemoveValue`, `InvalidJSON`, `InvalidJinja`) when values are missing or rendering fails. The `hydrate()` function removes keys with `RemoveValue` and propagates error placeholders unless `raise_on_error=True` in the context.

## Anti-Patterns

- **Don't use `jinja` kind and expect a typed value** — it always returns a string. Use `json` + `jinja` + `| tojson` for type preservation.
- **Don't add server imports to utility modules** — these are used client-side too. `HydrationContext.build()` is an exception (async, server-only) but the rest of `hydration.py` must remain importable without a running server.

## Pitfalls

- `maybe_template(s)` (in `templating.py`) only checks whether a string looks like it contains a Jinja expression — it does not validate that it's well-formed. A string with `{{` but no `}}` returns `True`.
- `HydrationContext` workspace variables are loaded once at build time. Stale contexts don't reflect variable updates made after context creation.
- **Non-UTF-8 subprocess output is silently replaced.** `consume_process_output` and `stream_text` (via `TextReceiveStream(errors="replace")`) replace invalid bytes with the Unicode replacement character `\ufffd` rather than raising. If captured output contains `\ufffd`, the subprocess emitted bytes that were not valid UTF-8.
- **`parameters_to_args_kwargs` adjusts the positional/keyword split based on the wrapper's signature, not the wrapped function's.** For `@functools.wraps`-decorated callables, it inspects the *wrapper* (via `follow_wrapped=False`) to count how many positional slots are actually available and routes excess parameters to `**kwargs`. This means `args` and `kwargs` from this function are shaped for the *wrapper* call, not the inner function — callers must not assume all POSITIONAL_OR_KEYWORD parameters end up in `args`.
- **`parameters_to_args_kwargs` skips the positional-to-keyword rewrite entirely when the function signature contains `*args`.** Inserting KEYWORD_ONLY parameters before a VAR_POSITIONAL parameter is invalid in Python, so the original signature is used as-is in that case.
- **Passing the same key in both an explicit parameter and a `**kwargs` dict raises `TypeError`.** `parameters_to_args_kwargs` detects when a VAR_KEYWORD (`**kwargs`) dict contains a key that also appears as an explicit parameter and raises rather than silently letting the variadic entry win. Exception: POSITIONAL_ONLY parameters are exempt because `fn(1, **{'a': 2})` is legal when `a` is positional-only.
