# templating

Placeholder detection and value application for Prefect's `{{ }}` templating used in block references, workspace variables, and parameter templating.

## Purpose & Scope

Finds `{{ ... }}` placeholders inside nested structures (`find_placeholders`) and substitutes their resolved values back in (`apply_values`). Distinguishes between standard placeholders, block-document references, and environment variable placeholders via `PlaceholderType`.

Note: this module is *not* a Jinja renderer. For Jinja hydration of `__prefect_kind: "jinja"` structures, see `../schema_tools/`. For user-facing Jinja templates in automation actions, see `prefect/server/utilities/user_templates.py`.

## Entry Points

- `find_placeholders(template) -> set[Placeholder]` — walk any dict/list/str and collect `{{ name }}` placeholders, classified by `PlaceholderType`.
- `apply_values(template, values) -> template` — substitute resolved values back into the nested structure.
- `determine_placeholder_type(name) -> PlaceholderType` — classify a placeholder name as STANDARD / BLOCK_DOCUMENT / ENV_VAR.

## Pitfalls

_No pitfalls documented yet._
