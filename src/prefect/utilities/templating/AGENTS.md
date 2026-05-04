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

- **`resolve_block_document_references` raises `ValueError` for malformed block placeholders.** Placeholders must follow the format `prefect.blocks.<block-type-slug>.<block-document-name>` (at least two dot-separated parts after the prefix). A placeholder like `{{ prefect.blocks.only-type }}` (missing the document name) raises `ValueError` before any network call is made.
- **Inline vs. whole-string block resolution behave differently.** When a block placeholder is the *entire* string value (`"{{ prefect.blocks.secret.my-token }}"`), the resolved value is returned as-is — it can be a `dict`, `list`, or scalar. When a block placeholder is *embedded* in surrounding text (`"{{ prefect.blocks.secret.my-token }}/my-image"`), the value is coerced to `str`; if it resolves to a `dict` or `list`, a `ValueError` is raised. A template string can mix block placeholders and standard `{{ variable }}` placeholders — non-block placeholders are left intact for later resolution.
