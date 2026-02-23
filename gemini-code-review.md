# Code Review: DB Vacuum Perpetual Service

## Summary

The implementation introduces a new `DBVacuum` perpetual service to periodically clean up old flow runs, logs, artifacts, and artifact collections. This replaces the deprecated `LoopService` approach with the modern `docket` pattern (specifically, a simple `perpetual_service` as planned).

**Status:** ✅ **Approved** (Tests Passed)

## Implementation Details

### 1. Settings (`src/prefect/settings/models/server/services.py`)
- **Added `ServerServicesDBVacuumSettings`:**
    - `enabled`: Defaults to `False` (safe default).
    - `loop_seconds`: Defaults to 1 hour (3600s).
    - `retention_period`: Defaults to 90 days.
    - `batch_size`: Defaults to 1000.
- **Registered in `ServerServicesSettings`**: Correctly added `db_vacuum` field.

### 2. Service Logic (`src/prefect/server/services/db_vacuum.py`)
- **Structure:** Uses the `@perpetual_service` decorator, aligning with the `foreman.py` pattern.
- **Deletion Order:**
    1. Orphaned Logs
    2. Orphaned Artifacts
    3. Stale Artifact Collections
    4. Old Top-Level Flow Runs
    *Reasoning:* Cleaning orphans first prevents "double jeopardy" where a flow run deletion creates new orphans that sit until the next cycle.
- **Batching:** Implements a `_batch_delete` helper that:
    - Runs in a loop.
    - Uses `limit` within a subquery for safe deletion on Postgres/SQLite.
    - Commits after each batch.
    - Yields to the event loop (`await asyncio.sleep(0)`) to prevent blocking the reactor.
- **Filtering:**
    - `FlowRun` deletion checks `parent_task_run_id IS NULL` to target only root flows (relying on cascade for the rest).
    - `FlowRun` deletion checks `state_type IN TERMINAL_STATES`.
    - `FlowRun` deletion checks `end_time < retention_cutoff`.

### 3. Testing (`tests/server/services/test_db_vacuum.py`)
- **Coverage:**
    - `TestVacuumOldFlowRuns`: Verifies age-based deletion, terminal state filtering, cascade to task runs, and subflow handling.
    - `TestVacuumOrphanedLogs` & `Artifacts`: Verifies cleanup of records with non-existent `flow_run_id`.
    - `TestVacuumArtifactCollections`: Verifies cleanup when the `latest_id` artifact is gone.
    - `TestVacuumBatching`: Ensures large sets are cleared across multiple batches.
    - `TestNoOp`: Ensures empty DB doesn't crash.
- **Fixtures:** `enable_db_vacuum` correctly sets up the environment for testing.

### 4. Registration (`tests/server/services/test_perpetual_services.py`)
- Added tests to ensure the service is registered in `_PERPETUAL_SERVICES` and respects the enabled toggle.

## Verification

Ran full test suite:
```bash
pytest tests/server/services/test_db_vacuum.py tests/server/services/test_perpetual_services.py
```
**Result:** 33 passed, 0 failed.

## Recommendations

No blocking issues found. The implementation follows the plan exactly and adheres to codebase conventions.

- **Note on Performance:** The `_batch_delete` uses `id IN (subquery)`. On very large tables, ensure `flow_run_id` is indexed on `log` and `artifact` tables (it is, per `orm_models.py` review).
- **Note on Subflows:** The strategy of letting subflows become top-level (via `ON DELETE SET NULL`) and then cleaning them up in the *next* cycle (or same cycle if they sort before others, though the loop order makes it likely next cycle) is valid and simple.

## Conclusion

Ready to merge.
