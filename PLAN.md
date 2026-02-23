# DB Vacuum Perpetual Service — Implementation Plan (v2)

*Updated after review by Opus Critic, Codex, and Gemini.*

---

## Background: Key Concepts

If you're new to this codebase, here's what you need to know:

### What is Docket?

Docket is Prefect's background job scheduler. Think of it like a cron system built into the server. Instead of having long-running Python classes that loop forever (the old `LoopService` pattern), Prefect now uses **docket** to schedule async functions that run periodically.

You write a normal `async def` function, decorate it with `@perpetual_service(...)`, and docket takes care of:
- Running it on a schedule (e.g., every 5 minutes, every hour)
- Making sure only one instance runs at a time (important when multiple servers are running)
- Restarting it if it crashes

### What is a Perpetual Service?

A perpetual service is just a decorated async function registered with docket. There are two patterns in the codebase:

1. **Pure perpetual** (what we're using) — A single function does all the work itself. Example: `foreman.py` checks worker health directly.

2. **Find-and-flood** — A "monitor" function finds work to do, then schedules individual docket tasks for each item. Example: `late_runs.py` finds late runs, then schedules a separate `mark_flow_run_late()` task for each one.

We're using pattern #1 because vacuum is a bulk operation — it would be wasteful to schedule thousands of individual "delete this one row" tasks.

### How Flow Runs Relate to Other Tables

```
Flow Run (the main thing we're deleting)
  ├── Task Runs          — auto-deleted (DB cascade)
  │     └── Task Run States  — auto-deleted (DB cascade)
  ├── Flow Run States    — auto-deleted (DB cascade)
  ├── Flow Run Inputs    — auto-deleted (DB cascade)
  ├── Logs               — NOT auto-deleted (no foreign key!)
  ├── Artifacts          — NOT auto-deleted (no foreign key!)
  │     └── Artifact Collections  — NOT auto-deleted (tracks "latest" artifact per key)
  └── Subflow Runs       — NOT deleted, but their parent_task_run_id is set to NULL
                           (they become "top-level" and get picked up next cycle)
```

**The key insight**: When we delete a flow run, some related data is cleaned up automatically by the database (cascade deletes), but logs, artifacts, and artifact collections are NOT — we have to clean those up ourselves.

### What is `ArtifactCollection`?

Artifacts in Prefect can be versioned — you might produce an artifact with key `"my-report"` on every flow run. The `artifact` table stores every version. The `artifact_collection` table is a shortcut that points to the *latest* version of each artifact key via a `latest_id` column. If we delete artifacts without updating `artifact_collection`, we leave dangling pointers (the collection points to an artifact that no longer exists).

---

## Context

PR [#19280](https://github.com/PrefectHQ/prefect/pull/19280) (by @levzem) added a `DBVacuum` LoopService. The maintainer (@zzstoatzz) asked for it to use docket instead. Lev hasn't returned since December 2025. We're taking it over.

**Goal:** Add a `db_vacuum` perpetual service that periodically deletes old flow runs, orphaned logs, orphaned artifacts, and stale artifact collections past a configurable retention period.

---

## Files to Create/Modify

### 1. Settings — `src/prefect/settings/models/server/services.py`

Add a `ServerServicesDBVacuumSettings` class (after `ServerServicesCancellationCleanupSettings`, ~line 45):

| Setting | Type | Default | Why |
|---------|------|---------|-----|
| `enabled` | `bool` | `False` | **Must be off by default** — maintainer explicitly requested this since it's a destructive service |
| `loop_seconds` | `float` | `3600` | Run hourly. Vacuum is heavy; no need to run every few seconds like other services |
| `retention_period` | `SecondsTimeDelta` | `timedelta(days=90)` | How old a flow run must be before deletion. Env var accepts seconds (e.g., `7776000` for 90 days). Uses `SecondsTimeDelta` for consistency with `late_runs.after_seconds` |
| `batch_size` | `int` | `1000` | Records per DB transaction. Lowered from the original 10,000 because deleting one flow run cascades to many task runs — a batch of 1,000 flow runs could mean 10,000+ actual row deletes |

All settings get `gt=0` validation to prevent misconfiguration (zero or negative values). `retention_period` gets a minimum floor of 1 hour to prevent accidental mass deletion.

Env var aliases follow the existing pattern:
- `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED`
- `PREFECT_SERVER_SERVICES_DB_VACUUM_LOOP_SECONDS`
- `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD`
- `PREFECT_SERVER_SERVICES_DB_VACUUM_BATCH_SIZE`

Register in `ServerServicesSettings` (between `cancellation_cleanup` and `event_persister`).

### 2. Service — `src/prefect/server/services/db_vacuum.py` (new file)

This is the core of the feature. One decorated async function + private helpers.

#### Main function

```python
@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.db_vacuum.enabled,
)
async def vacuum_old_resources(
    perpetual: Perpetual = Perpetual(automatic=False, every=timedelta(...)),
) -> None:
```

#### Deletion order (orphans first, then flow runs)

We chose **orphans first** because it's more resilient to interruptions:

1. **Orphaned logs** — logs whose `flow_run_id` points to a flow run that no longer exists
2. **Orphaned artifacts** — same pattern as logs
3. **Stale artifact collections** — collections whose `latest_id` points to an artifact that no longer exists
4. **Old top-level flow runs** — the main event: delete flow runs that finished more than 90 days ago

**Why this order?** If a previous vacuum cycle deleted flow runs but crashed before cleaning up orphans, this ordering catches those leftover orphans first. New orphans created by step 4 will be caught in the *next* cycle. This means at most one cycle of delay, but zero data is left permanently orphaned.

#### Batch delete helper

```python
async def _batch_delete(db, model, condition, batch_size) -> int:
    """Delete matching rows in batches. Each batch gets its own DB transaction."""
    total = 0
    while True:
        async with db.session_context(begin_transaction=True) as session:
            subquery = sa.select(model.id).where(condition).limit(batch_size).scalar_subquery()
            result = await session.execute(sa.delete(model).where(model.id.in_(subquery)))
            deleted = result.rowcount
        if deleted == 0:
            break
        total += deleted
        await asyncio.sleep(0)  # yield to event loop between batches
    return total
```

Key design decisions:
- **One session per batch** — each batch is its own transaction. If the service crashes mid-way, already-committed batches stay deleted (which is fine — they were supposed to be deleted anyway).
- **`asyncio.sleep(0)` between batches** — yields to the event loop so other async tasks (like API requests) aren't starved during a large vacuum.

#### Flow run deletion filters

```python
condition = sa.and_(
    db.FlowRun.parent_task_run_id.is_(None),     # only top-level runs
    db.FlowRun.state_type.in_(TERMINAL_STATES),   # only finished runs
    db.FlowRun.end_time.is_not(None),             # must have an end time
    db.FlowRun.end_time < retention_cutoff,        # older than retention period
)
```

Why each filter matters:
- **`parent_task_run_id IS NULL`** — only delete top-level flow runs. Subflows are handled indirectly (see "How subflows work" below).
- **`TERMINAL_STATES`** (COMPLETED, FAILED, CANCELLED, CRASHED) — never touch running, paused, or scheduled runs. This also means we **don't need concurrency slot cleanup** — only non-terminal runs hold concurrency slots.
- **`end_time`** not `created` — a run created 100 days ago but still running should NOT be deleted. We measure age from when it *finished*. (The `end_time` column has a descending index: `ix_flow_run__end_time_desc`.)

#### Orphan detection: `NOT EXISTS` instead of `NOT IN`

```python
# For logs:
existing_flow_run = sa.select(sa.literal(1)).where(db.FlowRun.id == db.Log.flow_run_id)
condition = sa.and_(
    db.Log.flow_run_id.is_not(None),
    ~sa.exists(existing_flow_run),
)
```

We use `NOT EXISTS` instead of `NOT IN` because:
- `NOT IN` has a [known SQL gotcha with NULLs](https://wiki.postgresql.org/wiki/Don%27t_Do_This#Don.27t_use_NOT_IN) — if the subquery returns any NULL, the entire `NOT IN` evaluates to UNKNOWN and returns no rows.
- `NOT EXISTS` is explicit, NULL-safe, and typically better for the query planner.

#### Artifact collection cleanup

After deleting orphaned artifacts, we clean up `artifact_collection` rows whose `latest_id` points to a now-deleted artifact:

```python
existing_artifact = sa.select(sa.literal(1)).where(db.Artifact.id == db.ArtifactCollection.latest_id)
condition = ~sa.exists(existing_artifact)
```

This is simpler than the per-artifact approach in `models/artifacts.py:delete_artifact()` (which finds the "next latest" version). In vacuum context, if the latest artifact is gone, all older artifacts for that key are likely gone too — so we just delete the collection row.

#### How subflows work (the two-cycle guarantee)

This is subtle but important:

```
Cycle 1: Delete parent flow run
  → DB cascade deletes the parent's task runs
  → Subflow's parent_task_run_id gets SET NULL (because the task run it pointed to was deleted)
  → Subflow is now "top-level" (parent_task_run_id = NULL)
  → But subflow is NOT deleted yet (it wasn't matched by our query in this cycle)

Cycle 2: The subflow is now top-level, terminal, and old enough
  → Gets picked up by the same flow run deletion query
  → Deleted along with its own task runs, etc.
```

This means deeply nested flows (flow → subflow → sub-subflow) take multiple cycles to fully clean up. That's by design — it keeps each cycle's transaction size predictable.

#### Logging

Every cycle logs what it did:

```python
logger.info(
    "Database vacuum completed: deleted %d flow runs, %d orphaned logs, "
    "%d orphaned artifacts, %d stale artifact collections.",
    flow_runs_deleted, logs_deleted, artifacts_deleted, collections_deleted,
)
```

When nothing was deleted: `logger.debug("Database vacuum completed: nothing to delete.")`

#### Scope exclusion: task-run-only logs and artifacts

Some logs and artifacts have `task_run_id` set but `flow_run_id = NULL` (from autonomous task runs). These are **out of scope** for this service. Our orphan detection only looks at `flow_run_id`. Adding task-run orphan detection would require a separate `NOT EXISTS` against the `task_run` table — we can add this later if needed.

#### Concurrent safety

If two server instances run vacuum simultaneously, they might try to delete the same rows. This is safe because:
- `DELETE WHERE id IN (...)` is idempotent — if another instance already deleted the row, the delete simply affects 0 rows.
- Each batch is its own short transaction, so no long-held locks.

### 3. Registration — `src/prefect/server/services/__init__.py`

Add one import line:
```python
import prefect.server.services.db_vacuum
```

This import triggers the `@perpetual_service` decorator, which registers the function in the global `_PERPETUAL_SERVICES` list. Without this import, docket would never know about our service.

### 4. Tests — `tests/server/services/test_db_vacuum.py` (new file)

Tests call `vacuum_old_resources()` directly — no docket mocking needed.

| Test Class | What it covers |
|-----------|----------------|
| **TestVacuumOldFlowRuns** | Deletes old completed runs; preserves recent runs; preserves running runs; cascade-deletes task runs; two-cycle subflow cleanup |
| **TestVacuumOrphanedLogs** | Deletes orphaned logs; preserves logs with existing flow runs; preserves logs with `flow_run_id=NULL` |
| **TestVacuumOrphanedArtifacts** | Deletes orphaned artifacts; preserves artifacts with existing flow runs; preserves artifacts with `flow_run_id=NULL` |
| **TestVacuumArtifactCollections** | Deletes stale collection rows after artifact cleanup; preserves valid collection rows |
| **TestVacuumBatching** | With `batch_size=5`, all 12 old flow runs are eventually deleted (verifies final state, not just first batch) |
| **TestNoOp** | Empty DB doesn't error |

**Autouse fixture**: `enable_db_vacuum` monkeypatches `enabled=True`, `retention_period=timedelta(days=1)`, `batch_size=100` for all tests.

### 5. Registration Tests — `tests/server/services/test_perpetual_services.py`

Add two tests:
- `test_db_vacuum_service_registered` — verifies `vacuum_old_resources` is in the global registry
- `test_db_vacuum_disabled_by_default` — verifies `enabled_getter()` returns `False`

---

## Implementation Order

1. **Settings** (`services.py`) — everything depends on this
2. **Service** (`db_vacuum.py`) — the core logic
3. **Registration** (`__init__.py`) — one-line import
4. **Tests** (`test_db_vacuum.py` + `test_perpetual_services.py`)

## Verification

```bash
# Run vacuum-specific tests
pytest tests/server/services/test_db_vacuum.py -v

# Run registration tests
pytest tests/server/services/test_perpetual_services.py -v

# Run all service tests to check for regressions
pytest tests/server/services/ -v
```

---

## Review Feedback Addressed

| Issue | Source | Resolution |
|-------|--------|------------|
| `ArtifactCollection` dangling pointers | Opus, Codex | Added artifact collection cleanup as step 3 |
| `NOT IN` NULL footgun | Opus, Codex | Switched to `NOT EXISTS` |
| Unbounded cascade size | Codex | Lowered default batch_size from 10,000 to 1,000 |
| Session management unclear | Opus | Specified: one `db.session_context()` per batch |
| Settings validation | Codex | Added `gt=0` on all fields, minimum floor on retention |
| Missing logging | Opus, Codex | Added logging spec |
| Sleep between batches | Gemini | Added `asyncio.sleep(0)` |
| `end_time` index check | Gemini | Confirmed: `ix_flow_run__end_time_desc` exists |
| task-run-only orphans | Opus | Documented as out of scope |
| Concurrent safety | Codex | Documented idempotent delete behavior |
| Subflow cascade chain | Opus | Clarified the FlowRun→TaskRun(cascade)→SET NULL chain |
| Deletion order | Codex vs Plan | Kept orphans-first for interruption resilience |
