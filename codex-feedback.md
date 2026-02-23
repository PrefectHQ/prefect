# Feedback on `PLAN.md` (DB Vacuum Perpetual Service)

## Overall
The plan is directionally solid and aligns with the current docket/perpetual architecture. The scope is reasonable, and defaulting the service to disabled is the right call.

## High-priority suggestions
1. Preserve `ArtifactCollection` consistency when deleting artifacts.
Deleting from `artifact` directly can leave stale `artifact_collection.latest_id` pointers. Current delete semantics in `src/prefect/server/models/artifacts.py` maintain this relationship. I strongly recommend either:
- deleting artifacts via model logic that updates `ArtifactCollection`, or
- adding explicit follow-up reconciliation for `artifact_collection` after bulk artifact deletes.

2. Reconsider deletion order to maximize same-cycle cleanup.
Your order is orphan logs/artifacts first, then old flow runs. That guarantees newly orphaned rows survive until the next cycle. Running old flow-run deletion first, then orphan logs/artifacts, gives better immediate cleanup and reduces accumulation.

3. Avoid `NOT IN` for orphan detection; prefer `NOT EXISTS`.
`NOT EXISTS` is generally safer and often more planner-friendly across SQLite/Postgres. For orphan checks (`log` / `artifact` against `flow_run`), `NOT EXISTS` is the safer default.

4. Bound cascade size by task runs, not just parent flow-run count.
A flow-run batch limit can still trigger very large cascades if one parent has many task runs. The previous PR's idea of limiting by joined task rows is better for transaction/lock predictability.

5. Add strict validation on new settings.
Use `gt=0` for `loop_seconds`, `batch_size`, and retention duration settings to prevent accidental invalid configs.

## Medium-priority suggestions
1. Use `timedelta`-style retention unless there is a clear compatibility need for seconds-only input.
`server.events.retention_period` already uses `timedelta`; matching this pattern keeps config UX consistent.

2. Add structured logging for each vacuum cycle.
Log cutoff, configured limits, and per-table delete counts. This will help operators tune retention/batch settings safely.

3. Add a regression test specifically for `ArtifactCollection`.
Include a case where the latest artifact for a key is deleted by vacuum and assert `ArtifactCollection.latest_id` remains valid (or the row is removed when no versions remain).

4. Add tests for multi-cycle nested subflow deletion behavior.
You mention eventual deletion across cycles; make that explicit in tests so this behavior stays stable during refactors.

## Registration/testing notes
1. Adding `src/prefect/server/services/db_vacuum.py` import to `src/prefect/server/services/__init__.py` is important for decorator registration side effects.
2. The proposed `tests/server/services/test_perpetual_services.py` additions look good; include the disabled-by-default assertion exactly as planned.

## Suggested acceptance criteria additions
1. No stale `artifact_collection.latest_id` references after vacuum.
2. Vacuum run is idempotent and safe when run concurrently.
3. Vacuum can process large backlogs without long transactions (batch behavior verified).
