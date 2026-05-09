# Utilities

General-purpose helpers and cross-cutting tools used throughout the Prefect SDK and server.

## Purpose & Scope

Shared utilities: data manipulation, async helpers, schema tooling, callables introspection, and infrastructure helpers. These modules have no common theme beyond being broadly reused — if something is self-contained and used across two or more subsystems, it lives here.

Does NOT include: server-specific utilities (`server/utilities/`), concurrency slot management (`concurrency/`), or logging infrastructure (`logging/`).

## Cross-cutting rules

- **Don't add server imports to utility modules.** Everything here is used client-side too. `HydrationContext.build()` in `schema_tools/` is an explicit, documented exception (async, server-only); no new server-touching code should creep into other modules.

## Subpackages (focused intent nodes)

Each subpackage owns its own `AGENTS.md` with entry points and pitfalls specific to that domain.

- `schema_tools/` → Hydration and validation of `__prefect_kind` template structures (see `schema_tools/AGENTS.md`)
- `processutils/` → Subprocess execution, output streaming, and command serialization (see `processutils/AGENTS.md`)
- `callables/` → Function signature introspection, parameter coercion, parameter schema generation (see `callables/AGENTS.md`)
- `asyncutils/` → Async/sync bridging, thread coordination, concurrency primitives (see `asyncutils/AGENTS.md`)
- `templating/` → Placeholder detection and value application for Prefect's `{{ }}` templating (see `templating/AGENTS.md`)
- `engine/` → Result-to-state linking, SIGTERM bridge management, and control-intent coordination (see `engine/AGENTS.md`)
- `filesystem/` → File filtering, path normalization, `tmpchdir` (see `filesystem/AGENTS.md`)

## Flat modules

These modules have no dedicated intent node yet. Promote any one of them to a subpackage (`foo.py` → `foo/__init__.py` + `foo/AGENTS.md`) when non-obvious invariants accrue — the import path is preserved.

- `annotations.py` — Custom Prefect type annotations used in flow/task signatures (`unmapped`, `allow_failure`, `quote`, `NotSet`)
- `collections.py` — Extended collection helpers (`visit_collection`, `flatten`, `remove_nested_keys`)
- `dispatch.py` — Dynamic type dispatch registry
- `importtools.py` — Dynamic imports, aliased module loading, script-to-module conversion
- `pydantic.py` — Pydantic v1/v2 compatibility shims, custom serializers, type dispatch integration
- `hashing.py` — Stable hashing (`stable_hash`, `file_hash`, `hash_objects`)
- `dockerutils.py` — Docker image building, Python version detection, Docker client helpers
- `timeout.py` — Timeout context managers for async/sync code
- `services.py` — Client metrics server and resilient service loop with backoff
- `visualization.py` — Flow/task graph visualization via Graphviz (`build_task_dependencies`) or Mermaid (`build_mermaid_dependencies`); the Mermaid path has no system dependency
- `urls.py` — URL validation and UI path formatting
- `names.py` — Slug generation and obfuscation helpers
- `math.py` — Distribution sampling and clamping utilities
- `text.py` — String truncation and fuzzy matching
- `context.py` — Context variable accessors
- `compat.py` — Python version compatibility shims
- `slugify.py` — Thin wrapper around `unicode-slugify`
- `generics.py` — Generic type validation
- `render_swagger.py` — MkDocs plugin for rendering Swagger/OpenAPI schemas

Private (`_`-prefixed):

- `_engine.py` — Naming and hook-resolution helpers for custom flow/task run names
- `_infrastructure_exit_codes.py` — Registry of exit-code explanations for infrastructure processes
