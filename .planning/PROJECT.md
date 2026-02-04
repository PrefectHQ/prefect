# Bundle Include Files for Infrastructure Decorators

## What This Is

A feature for Prefect's infrastructure decorators (starting with `@ecs`) that allows users to include arbitrary non-Python files in deployment bundles. Users can specify files, directories, and glob patterns via an `include_files` kwarg, and those files are bundled alongside Python code so they're available when flows run in remote environments.

## Core Value

Flows that depend on non-Python files (config, templates, data files) must have those files available in their remote execution environment without requiring users to manage separate file distribution.

## Requirements

### Validated

(Existing Prefect capabilities this builds on)

- ✓ Infrastructure decorators exist (`@ecs`, `@kubernetes`, etc.) — existing
- ✓ Bundle creation and deployment system exists — existing
- ✓ `.prefectignore` pattern matching exists — existing

### Active

- [ ] `@ecs` decorator accepts `include_files` kwarg
- [ ] `include_files` accepts list of strings: files, directories, glob patterns
- [ ] Paths resolve relative to the flow file's directory
- [ ] Included files preserve relative directory structure in bundle
- [ ] `.prefectignore` patterns are respected when resolving include paths
- [ ] Missing/unmatched paths emit warning at deployment time (not error)

### Out of Scope

- Other infrastructure decorators (`@kubernetes`, `@modal`, etc.) — will add after validating with user
- Size limits or file type restrictions — not needed for initial implementation
- Compression or optimization of included files — bundle system handles this

## Context

- A user requested this feature specifically for `@ecs` deployments
- Use case: flows depend on config files, templates, or data files that need to be available at runtime
- Starting with `@ecs` to validate the approach before expanding to other decorators
- Prefect already has bundle infrastructure and `.prefectignore` support to build on

## Constraints

- **Scope**: `@ecs` decorator only for initial implementation — validate with requesting user first
- **Compatibility**: Must work with existing bundle creation pipeline
- **Behavior**: Warn on missing files rather than fail — deployment should proceed

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Paths relative to flow file | Keeps deployments portable; matches user mental model | — Pending |
| Warn on missing files | Don't block deployments on typos; user can iterate | — Pending |
| Start with `@ecs` only | Validate approach before spreading to all decorators | — Pending |

---
*Last updated: 2026-02-03 after initialization*
