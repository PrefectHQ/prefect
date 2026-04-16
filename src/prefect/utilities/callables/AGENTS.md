# callables

Function signature introspection, parameter coercion, and JSON Schema generation for flow and task parameters.

## Purpose & Scope

Inspects user-written flow/task functions to produce:
- Bindable `args`/`kwargs` from a parameters dict (`parameters_to_args_kwargs`, `get_call_parameters`).
- JSON Schema representations of function signatures for UI parameter forms and server-side validation (`parameter_schema`).

## Entry Points

- `parameters_to_args_kwargs(fn, parameters) -> (args, kwargs)` — split a parameters dict into positional and keyword slots based on the function's signature.
- `get_call_parameters(fn, call_args, call_kwargs) -> dict` — inverse: bind actual call args/kwargs into a parameters dict.
- `parameter_schema(fn) -> ParameterSchema` — introspect the function signature into a Pydantic-backed JSON Schema.

## Pitfalls

- **`parameters_to_args_kwargs` adjusts the positional/keyword split based on the wrapper's signature, not the wrapped function's.** For `@functools.wraps`-decorated callables, it inspects the *wrapper* (via `follow_wrapped=False`) to count how many positional slots are actually available and routes excess parameters to `**kwargs`. This means `args` and `kwargs` from this function are shaped for the *wrapper* call, not the inner function — callers must not assume all POSITIONAL_OR_KEYWORD parameters end up in `args`.
- **`parameters_to_args_kwargs` skips the positional-to-keyword rewrite entirely when the function signature contains `*args`.** Inserting KEYWORD_ONLY parameters before a VAR_POSITIONAL parameter is invalid in Python, so the original signature is used as-is in that case.
- **Passing the same key in both an explicit parameter and a `**kwargs` dict raises `TypeError`.** `parameters_to_args_kwargs` detects when a VAR_KEYWORD (`**kwargs`) dict contains a key that also appears as an explicit parameter and raises rather than silently letting the variadic entry win. Exception: POSITIONAL_ONLY parameters are exempt because `fn(1, **{'a': 2})` is legal when `a` is positional-only.
