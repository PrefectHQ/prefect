# Heartbeat Event Pruner — Implementation Plan

*Separate service from the DB vacuum (PLAN.md). Can be implemented and shipped independently.*

---

## Background: Key Concepts

### The Problem

Every running flow run emits a `prefect.flow-run.heartbeat` event at a regular interval (configurable, defaults to 30 seconds). For a flow run that takes 1 hour, that's ~120 heartbeat events. For a run that takes a day, that's ~2,880. Multiply by hundreds of concurrent runs and the `events` table fills up fast with redundant data.

The existing event retention system (`event_persister.trim()`) deletes *all* events older than 7 days. But within that 7-day window, you could have millions of heartbeat events that are mostly noise — only the *latest* heartbeat per flow run matters (it tells you the run is still alive).

### How Events Work in Prefect

Events in Prefect are generic — they're not specific to flow runs. Any part of the system can emit events. They're stored in a single `events` table:

```
events table:
  id          — UUID primary key
  event       — text, e.g. "prefect.flow-run.heartbeat", "prefect.flow-run.completed"
  resource_id — text, e.g. "prefect.flow-run.abc-123-def"
  occurred    — timestamp, when the event happened
  payload     — JSON, event-specific data
  received    — timestamp, when the server got the event
  recorded    — timestamp, when it was persisted to DB
  follows     — optional UUID, for event ordering
```

**Important**: There is NO `flow_run_id` column on the events table. The flow run is identified by the `resource_id` field (e.g., `"prefect.flow-run.abc-123-def"` → flow run UUID `abc-123-def`).

### How Heartbeats Are Emitted

In `src/prefect/flow_engine.py` (line 372):
```python
emit_event(
    event="prefect.flow-run.heartbeat",
    resource={"prefect.resource.id": f"prefect.flow-run.{self.flow_run.id}", ...},
)
```

Each heartbeat creates a new row in `events` with:
- `event = "prefect.flow-run.heartbeat"`
- `resource_id = "prefect.flow-run.<flow_run_uuid>"`
- `occurred = <current timestamp>`

### Existing Indexes

The events table has a composite index that's perfect for our query:

```
ix_events__event_resource_id_occurred  ON (event, resource_id, occurred)
```

This means filtering by `event = 'prefect.flow-run.heartbeat'` and grouping by `resource_id` with ordering by `occurred` will be efficient.

### The EventResource Table

Each event also creates rows in `event_resources` (one per related resource — e.g., the parent flow, the deployment). The `event_resources` table has an `event_id` column (NOT a foreign key — same no-FK pattern as logs and artifacts). When we delete heartbeat events, we also need to delete their associated `event_resources` rows manually.

### What is a Perpetual Service?

(See PLAN.md for the full explanation.) In short: a decorated `async def` function that docket runs on a schedule. We use the "pure perpetual" pattern (like `foreman.py`) — one function does all the work, no fan-out to sub-tasks.

### Why a Separate Service from DB Vacuum?

- **Vacuum** = destructive, deletes entire flow runs and their data. Most people want to keep their history. Off by default.
- **Heartbeat pruning** = safe, removes redundant noise. Almost everyone benefits from this. On by default.

Many users will want heartbeat pruning *without* enabling the full vacuum. Separate services, separate toggles.

---

## Files to Create/Modify

### 1. Settings — `src/prefect/settings/models/server/services.py`

Add `ServerServicesHeartbeatPrunerSettings` class:

| Setting | Type | Default | Why |
|---------|------|---------|-----|
| `enabled` | `bool` | `True` | **On by default** — unlike vacuum, this is safe and universally beneficial. It only removes redundant copies of the same signal |
| `loop_seconds` | `float` | `600` | Run every 10 minutes. Heartbeats accumulate fast (~1 per flow run every 30 seconds), so pruning more frequently than vacuum makes sense |
| `batch_size` | `int` | `5000` | Events per batch. Safe to be higher than vacuum since there are no cascading deletes — each event row is standalone |

All settings get `gt=0` validation.

Env var aliases:
- `PREFECT_SERVER_SERVICES_HEARTBEAT_PRUNER_ENABLED`
- `PREFECT_SERVER_SERVICES_HEARTBEAT_PRUNER_LOOP_SECONDS`
- `PREFECT_SERVER_SERVICES_HEARTBEAT_PRUNER_BATCH_SIZE`

Register in `ServerServicesSettings`.

### 2. Service — `src/prefect/server/services/heartbeat_pruner.py` (new file)

```python
@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.heartbeat_pruner.enabled,
)
async def prune_heartbeat_events(
    perpetual: Perpetual = Perpetual(automatic=False, every=timedelta(...)),
) -> None:
```

**Two steps:**
1. **Deduplicate heartbeat events** — for each flow run, keep only the latest `prefect.flow-run.heartbeat` event, delete the rest
2. **Clean up orphaned event_resources** — delete `event_resources` rows that reference deleted heartbeat events

#### The Dedup Query

This uses a window function (`ROW_NUMBER`) to identify which heartbeat to keep per flow run:

```python
# Find the latest heartbeat event ID per flow run (resource_id)
latest_per_run = (
    sa.select(
        db.Event.id,
        sa.func.row_number().over(
            partition_by=db.Event.resource_id,
            order_by=db.Event.occurred.desc(),
        ).label("rn"),
    )
    .where(db.Event.event == "prefect.flow-run.heartbeat")
    .subquery()
)
keep_ids = sa.select(latest_per_run.c.id).where(latest_per_run.c.rn == 1)

# Delete all heartbeat events NOT in the "keep" set
condition = sa.and_(
    db.Event.event == "prefect.flow-run.heartbeat",
    ~db.Event.id.in_(keep_ids),
)
```

**How this works, step by step:**
1. The inner query looks at every heartbeat event and assigns a row number per `resource_id` (which is `"prefect.flow-run.<uuid>"`), ordered by `occurred DESC` — so row 1 is the most recent heartbeat for each flow run
2. `keep_ids` selects only the row-1 IDs (the latest heartbeat per flow run)
3. The delete condition matches all heartbeat events whose ID is NOT in `keep_ids`

**Index coverage**: The composite index `ix_events__event_resource_id_occurred` on `(event, resource_id, occurred)` covers the PARTITION BY and ORDER BY perfectly.

**SQLite compatibility**: `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` is supported in SQLite 3.25+ (2018). Prefect requires SQLite 3.35+, so this is safe.

#### Orphaned EventResource Cleanup

After deleting heartbeat events, clean up `event_resources` rows that reference deleted events:

```python
existing_event = sa.select(sa.literal(1)).where(db.Event.id == db.EventResource.event_id)
condition = sa.and_(
    db.EventResource.resource_id.like("prefect.flow-run.%"),
    ~sa.exists(existing_event),
)
```

**Note**: `EventResource.event_id` has NO foreign key constraint (verified in `orm_models.py:1462`) — same pattern as orphaned logs/artifacts in the vacuum plan. We must clean these up manually.

#### Batch Delete Helper

Same pattern as the event_persister's `batch_delete` (lines 42-74) and the vacuum service's `_batch_delete`:

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

The window function subquery (`keep_ids`) is re-evaluated each batch — as rows are deleted, the "latest per resource_id" stays correct.

**Note on sharing with vacuum**: Both services use the same `_batch_delete` pattern. For now, duplicate it in each service file to avoid cross-dependencies. If a third service needs it later, extract to a shared utility.

#### Logging

```python
logger.info(
    "Heartbeat pruning completed: removed %d duplicate heartbeat events, "
    "%d orphaned event resources.",
    events_deleted, resources_deleted,
)
```

When nothing was pruned: `logger.debug("Heartbeat pruning completed: nothing to prune.")`

#### Concurrent Safety

Same as the vacuum service — `DELETE WHERE id IN (...)` is idempotent. If two instances prune simultaneously, they'll just delete non-overlapping subsets (or one will find 0 rows and no-op).

### 3. Registration — `src/prefect/server/services/__init__.py`

Add one import line:
```python
import prefect.server.services.heartbeat_pruner
```

### 4. Tests — `tests/server/services/test_heartbeat_pruner.py` (new file)

| Test | What it covers |
|------|----------------|
| **test_keeps_latest_heartbeat_per_flow_run** | Create 10 heartbeats for one flow run → after pruning, only the latest remains |
| **test_handles_multiple_flow_runs** | Create heartbeats for 3 different flow runs → each keeps its own latest |
| **test_ignores_non_heartbeat_events** | Other event types (e.g., `prefect.flow-run.completed`) are untouched |
| **test_cleans_up_orphaned_event_resources** | EventResource rows for deleted heartbeat events are removed |
| **test_preserves_event_resources_for_kept_events** | EventResource rows for the kept (latest) heartbeat are preserved |
| **test_noop_with_no_heartbeats** | Empty events table doesn't error |
| **test_noop_with_single_heartbeat_per_run** | If each flow run has only 1 heartbeat, nothing is deleted |
| **test_batching** | With `batch_size=3`, all 20 duplicate heartbeats are eventually deleted (verifies final state) |

### 5. Registration Tests — `tests/server/services/test_perpetual_services.py`

```python
def test_heartbeat_pruner_service_registered():
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "prune_heartbeat_events" in service_names

def test_heartbeat_pruner_enabled_by_default():
    config = next(c for c in _PERPETUAL_SERVICES if c.function.__name__ == "prune_heartbeat_events")
    assert config.enabled_getter() is True
```

---

## Implementation Order

1. **Settings** (`services.py`) — prerequisite for everything
2. **Service** (`heartbeat_pruner.py`) — the core logic
3. **Registration** (`__init__.py`) — one-line import
4. **Tests** (`test_heartbeat_pruner.py` + `test_perpetual_services.py`)

## Verification

```bash
# Run pruner-specific tests
pytest tests/server/services/test_heartbeat_pruner.py -v

# Run registration tests
pytest tests/server/services/test_perpetual_services.py -v

# Run all service tests to check for regressions
pytest tests/server/services/ -v
```

---

## Key Reference Files

| File | What to look at |
|------|----------------|
| `src/prefect/server/services/foreman.py` | Primary pattern reference (pure perpetual service) |
| `src/prefect/server/events/services/event_persister.py` | `batch_delete()` helper (lines 42-74) and `trim()` function (lines 216-243) |
| `src/prefect/server/database/orm_models.py` | `Event` model (line 1396), `EventResource` model (line 1445), indexes |
| `src/prefect/flow_engine.py` | `_emit_flow_run_heartbeat()` (line 338) — how heartbeats are created |
| `src/prefect/settings/models/server/services.py` | Settings pattern for all existing services |
| `src/prefect/settings/models/server/events.py` | `retention_period` setting (line 92) — existing event retention config |
