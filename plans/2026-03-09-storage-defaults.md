# Storage Defaults

## Goal

Deliver predictable result-storage defaults in OSS by establishing and implementing this user-facing hierarchy:

```text
Explicit flow/task setting
  ↓
Work pool default
  ↓
OSS server default
  ↓
Server / local fallback
```

The outcome should be:

- users can persist results without repeating storage configuration in every flow or task
- platform teams can set defaults at the right administrative level
- work pools can still align storage with compute
- explicit flow and task configuration always wins

## Non-Goals

1. Shipping every hierarchy layer in one PR or one release
2. Changing the public `@flow` / `@task` result-storage API
3. Replacing existing work-pool storage configuration for bundle upload / execution
4. Planning or implementing Cloud-owned settings surfaces in this document
5. Building a new UI or CLI surface before the runtime resolution contract is settled
6. Changing task result persistence semantics beyond what is required to honor the hierarchy

## Background

### Product Direction

The Storage Defaults project is about moving users away from repeated per-flow storage configuration and toward scoped defaults that are:

- predictable
- overridable
- administratively manageable
- aligned with runtime environment

The project description already captures the intended user behavior. What the OSS repo still needs is an OSS implementation contract: where result-storage resolution actually happens today, what code paths participate in that decision, and how OSS-owned default layers should plug into those paths without creating more one-off behavior.

### Current State

Today, result-storage behavior is split across two different kinds of code paths:

1. **Runtime result-store resolution**
   - `src/prefect/results.py`
   - `ResultStore.update_for_flow()`
   - `ResultStore.update_for_task()`
   - `get_default_result_storage()`

2. **Ad-hoc submission-side mutation for work-pool defaults**
   - `src/prefect/flows.py`
   - `InfrastructureBoundFlow.submit_to_work_pool()`
   - `src/prefect/workers/base.py`
   - `BaseWorker._submit_adhoc_run()`

These paths are related but not unified.

### Existing Behavior By Layer

| Layer | Current State | Notes |
| --- | --- | --- |
| Explicit flow/task storage | Exists | `flow.result_storage` and `task.result_storage` are already supported |
| Work-pool default storage | Partial | `default_result_storage_block_id` exists, but only participates in ad-hoc submission paths |
| OSS server default storage | Missing | No first-class server-level default exists beyond global settings |
| Settings/local fallback | Exists | `PREFECT_RESULTS_DEFAULT_STORAGE_BLOCK` and local filesystem fallback exist today |

### External Constraint: Cloud Scope

Cloud account-level direct block references are not viable with the current data model:

- account settings live at account scope
- block documents live at workspace scope
- a direct `default_result_storage_block_id` at the account layer cannot point cleanly at a workspace-scoped block document

For OSS planning purposes, that means:

- OSS server-level defaults should be treated as the OSS analog of workspace-level defaults
- account-level Cloud inheritance should not be treated as an OSS planning deliverable
- any future cross-surface integration should assume Cloud account scope cannot directly store a workspace-scoped block-document ID

## Problem Statement

The project needs one clear runtime contract for result-storage precedence, but the current implementation is fragmented:

- normal runtime resolution happens in `results.py`
- work-pool defaults are applied by mutating flow objects before execution in two ad-hoc submission paths
- settings-based defaults are part of the result-store path, not the work-pool path

If we start adding new OSS default layers without resolving that fragmentation, we will be stacking new behavior on top of:

- duplicated precedence logic
- inconsistent entrypoints
- unclear ownership between submission-time mutation and runtime resolution

## User Stories

### 1. Platform Defaults

A self-hosted operator wants to set result storage once for an environment so that new flows persist results without every codebase repeating storage configuration.

### 2. Compute-Aligned Overrides

A team uses multiple work pools with different runtime environments and wants each pool to default to storage that is reachable from that compute environment.

### 3. Explicit Escape Hatch

A flow or task author wants to override every default and select result storage directly in code.

## Required Contract

The runtime contract for this project should be:

1. Explicit task storage wins over everything else for that task.
2. Explicit flow storage wins over any lower-precedence default for that flow.
3. A work-pool default may apply only when no higher-precedence configured storage applies for that flow run.
4. OSS server defaults are lower precedence than work-pool defaults.
5. Settings/local fallback remains the final fallback behavior.

Two additional rules need to be made explicit:

1. **Runtime entrypoints must agree**
   - flow engine
   - task engine
   - ad-hoc submission entrypoints

2. **Local storage needs a clear meaning**
   - local filesystem can represent explicit user intent
   - local filesystem can also represent fallback behavior
   - ad-hoc remote submission cannot treat those two cases identically if the goal is retrievable remote results

## Current Code Paths

### Runtime Resolution

These code paths already participate in result-store construction:

- `src/prefect/results.py`
  - `get_default_result_storage()`
  - `resolve_result_storage()`
  - `ResultStore.update_for_flow()`
  - `ResultStore.update_for_task()`

- `src/prefect/flow_engine.py`
  - constructs flow-run contexts using `get_result_store().update_for_flow(...)`

- `src/prefect/task_engine.py`
  - constructs task contexts using `get_result_store().update_for_task(...)`

This is the natural home for runtime precedence.

### Ad-Hoc Submission Paths

These code paths currently decide whether a work-pool default should override missing storage:

- `src/prefect/flows.py`
  - `InfrastructureBoundFlow.submit_to_work_pool()`

- `src/prefect/workers/base.py`
  - `BaseWorker._submit_adhoc_run()`

These are not general runtime paths. They are specific to ad-hoc bundle submission and exist to make remote results retrievable when users dispatch flows without already configuring storage.

### Configuration Surfaces

- `src/prefect/settings/models/results.py`
  - `default_storage_block`
- `src/prefect/client/schemas/objects.py`
  - `WorkPoolStorageConfiguration.default_result_storage_block_id`
- `src/prefect/server/schemas/core.py`
  - work-pool storage configuration schema
- `src/prefect/cli/work_pool.py`
  - work-pool storage configuration commands

## Design Decisions

### 1. Treat This As One Product Contract, Not One Implementation Path

The hierarchy is one user-facing contract, but it does not imply that every layer must be applied in the same place in the same release.

We should separate:

- **runtime precedence contract**
- **submission-time compatibility behavior**
- **administrative configuration surfaces**

### 2. Keep Runtime Resolution in `results.py`

The engines already construct result stores through `ResultStore.update_for_flow()` and `ResultStore.update_for_task()`. That is the right long-term seam for OSS server defaults and any future lower-precedence layers.

The project should converge on runtime resolution owned by `results.py`, not continue to accumulate one-off precedence logic in submission entrypoints.

### 3. Treat Work-Pool Defaults As Transitional, But Real

Work-pool defaults already exist and already matter to users. They are currently implemented as submission-time mutation for ad-hoc submission.

The project should not pretend they are already part of the main result-store resolution path. Instead:

- preserve their current user value
- define exactly where they fit in the hierarchy
- migrate them into the broader resolution model deliberately

### 4. Keep Cloud Dependencies As External Inputs

OSS server defaults are a concrete next step.

Cloud workspace/account defaults are still relevant constraints, but they are not OSS-owned execution items in this document:

- they inform how we describe the hierarchy
- they should not block OSS server-default work
- they belong in separate planning and implementation work outside this repo

### 5. Prefer Small, Hierarchy-Shaped Deliveries

Each implementation slice should map cleanly to the hierarchy:

- protect explicit-over-default precedence
- clarify when work-pool defaulting may apply
- add OSS server defaults

PRs that do not visibly advance one of those steps should be considered optional cleanup, not project-critical.

## Implementation Plan

### Phase 1: Resolution Contract

**Outcome**: write down and implement the runtime contract for the OSS hierarchy without yet adding a new OSS server-level default.

**Deliverables**:

- document the precedence contract in code comments and tests
- identify the runtime seam that future defaults will plug into
- define how ad-hoc work-pool submission relates to that runtime seam
- preserve explicit-over-default precedence everywhere

**Specific work**:

- audit `ResultStore.update_for_flow()` and `ResultStore.update_for_task()` as the runtime resolution entrypoints
- decide whether ad-hoc submission continues to mutate flows before execution or delegates more directly to the runtime resolution path
- define what “configured storage” means for ad-hoc remote result retrieval
- ensure the sync and async engine paths remain aligned

**Status mapping**:

- primary issue: `OSS-7740`

### Phase 2: Work-Pool Integration

**Outcome**: make work-pool defaults a clearly-defined layer in the hierarchy instead of a special case with duplicated logic.

**Deliverables**:

- a single shared rule for when work-pool default result storage is eligible to apply
- a clear boundary between ad-hoc submission compatibility behavior and runtime resolution
- tests that prove work-pool defaulting only applies when higher-precedence configured storage is absent

**Specific work**:

- centralize the work-pool eligibility rule
- preserve current user-facing ad-hoc submission ergonomics
- avoid introducing abstract internal models that are broader than the actual rule being shared

**Status mapping**:

- primary issue: `OSS-7741`

### Phase 3: OSS Server-Level Default

**Outcome**: self-hosted users get a first-class shared default that plays the same conceptual role as a workspace default in Cloud.

**Deliverables**:

- server-level result-storage configuration surface
- runtime resolution integration for that server-level default
- compatibility story with `PREFECT_RESULTS_DEFAULT_STORAGE_BLOCK`

**Specific work**:

- decide whether the first implementation is:
  - a promoted setting built on `PREFECT_RESULTS_DEFAULT_STORAGE_BLOCK`, or
  - a separate first-class server-managed configuration surface
- ensure it plugs into the same runtime resolution contract defined in Phase 1
- provide tests for flow and task behavior

**Status mapping**:

- primary issue: `OSS-7739`

## Recommended Execution Order

1. `OSS-7740` — write and agree on the resolution contract
2. `OSS-7741` — clarify work-pool integration
3. `OSS-7739` — ship server-level default storage in OSS

## Architecture Questions To Resolve In Phase 1

### 1. What is the single runtime resolution seam?

Likely answer: `ResultStore.update_for_flow()` and `ResultStore.update_for_task()`

Needs confirmation:

- whether all relevant runtime paths already flow through those methods
- whether any ad-hoc submission path must remain outside that seam for compatibility reasons

### 2. How should ad-hoc submission interact with runtime resolution?

Options:

1. Keep submission-time mutation for work-pool defaults, but make its eligibility rule explicit and shared.
2. Move work-pool default application closer to runtime resolution in OSS.
3. Use a hybrid approach where ad-hoc submission passes lower-precedence candidates into runtime resolution instead of mutating the flow directly.

Recommendation for now:

- keep submission-time behavior narrow and compatible in the short term
- do not let it become the pattern for new default layers

### 3. What counts as “already configured” for remote retrieval?

This is the main subtlety in the current implementation.

For ad-hoc remote submission, there is a meaningful difference between:

- explicit flow storage
- inherited non-local storage from an existing result store
- local fallback behavior

That difference needs to be codified and tested.

### 4. What external assumptions should OSS make about future Cloud defaults?

OSS does not need to plan Cloud implementation here, but it does need to avoid painting the product into a corner.

The minimum assumptions to preserve are:

- Cloud workspace-level defaults conceptually map to the same hierarchy layer as OSS server-level defaults
- Cloud account inheritance is lower precedence than workspace scope
- Cloud account scope cannot be modeled as a direct block-document ID

### 5. Should tasks follow the same hierarchy as flows?

Likely yes, with the existing task-specific overrides preserved:

- explicit task storage
- inherited flow result-store behavior when task storage is not explicit
- lower-precedence defaults beneath that

This needs to be verified and documented, not assumed.

## Risks

### 1. Hidden Drift Between Sync and Async Paths

Any change to result-store resolution must keep:

- sync flow engine
- async flow engine
- sync task engine
- async task engine

in lockstep.

### 2. Work-Pool Behavior Can Keep Growing Sideways

The existing work-pool default path is useful, but if every new default layer copies its structure, the project will fail architecturally even if individual PRs look correct.

### 3. Local Storage Is Ambiguous

Local filesystem can mean:

- explicit user choice
- default settings behavior
- inherited context

Those meanings matter differently for remote execution and retrievable results.

### 4. External Cross-Surface Concerns Can Stall The OSS Project

If Cloud-specific planning is treated as a prerequisite for OSS server-default delivery, the OSS side of the project will move too slowly.

## Open Questions

1. Should users eventually be able to see which OSS level their resolved result storage came from?
2. Should invalid defaults fail fast at configuration time, runtime, or both?
3. Should work-pool defaults remain specific to ad-hoc submission, or become a general runtime layer for any OSS run associated with a work pool?
4. Is `PREFECT_RESULTS_DEFAULT_STORAGE_BLOCK` sufficient as the first OSS server-level implementation, or do we need a more explicit server-managed abstraction?
5. What external Cloud assumptions do we need to preserve so OSS server defaults remain conceptually aligned with workspace-level defaults elsewhere?

## Suggested Immediate Next Step

Use this plan as the design basis for `OSS-7740` and do not start additional implementation PRs until the following are explicitly agreed:

1. the runtime resolution seam
2. the role of ad-hoc submission in the hierarchy
3. the first OSS server-level delivery shape

Once those are agreed, the next implementation PR should target the first user-visible feature slice:

- either the minimum `OSS-7741` cleanup required to lock work-pool behavior into the contract, or
- the first concrete `OSS-7739` server-level default implementation if the contract is already clear enough
