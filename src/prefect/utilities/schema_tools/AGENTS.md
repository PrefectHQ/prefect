# schema_tools

Hydration and validation of `__prefect_kind` template structures used in deployment parameters and automation action payloads.

## Purpose & Scope

Resolves `__prefect_kind` structures into real Python values (hydration) and validates JSON Schema parameter specs with first-class support for Prefect's placeholder types (validation).

## Entry Point

```python
from prefect.utilities.schema_tools.hydration import hydrate, HydrationContext

ctx = HydrationContext(render_jinja=True, jinja_context={"event": event})
result = hydrate(parameters, ctx)
```

## `__prefect_kind` Contracts

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

## Placeholder Protocol

Handlers return `Placeholder` subclasses (e.g. `RemoveValue`, `InvalidJSON`, `InvalidJinja`) when values are missing or rendering fails. `hydrate()` removes keys with `RemoveValue` and propagates error placeholders unless `raise_on_error=True` in the context.

## Anti-Patterns

- **Don't use `jinja` kind and expect a typed value** — it always returns a string. Use `json` + `jinja` + `| tojson` for type preservation.
- **Don't add server imports to this module** — it's used client-side too. `HydrationContext.build()` is an explicit exception (async, server-only); the rest of `hydration.py` must remain importable without a running server.

## Pitfalls

- **`HydrationContext` workspace variables are loaded once at build time.** Stale contexts don't reflect variable updates made after context creation.
