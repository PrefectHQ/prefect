# Test Fixtures

Shared pytest fixtures used across the test suite, organized by concern.

## Key Contract

**Server-side and client-side fixtures serve different purposes and should not be mixed.**

- `prefect_client` / `sync_prefect_client` — Full SDK clients. For client-side tests.
- `client` / `test_client` — Raw HTTP clients against an ephemeral server. For server API tests.
- `session` — Async SQLAlchemy session. For server model/orchestration tests.

## Fixture Files

- **`api.py`** — Ephemeral FastAPI app and HTTP test clients
- **`client.py`** — SDK client fixtures (`prefect_client`, `sync_prefect_client`, `cloud_client`)
- **`database.py`** — Database session, pre-built ORM objects (`flow`, `flow_run`, `task_run`, `deployment`, `work_pool`, blocks, etc.), and `initialize_orchestration` for testing orchestration rules
- **`events.py`** — Event client fixtures
- **`time.py`** — `frozen_time`, `advance_time`. Hand-rolled patches of `prefect.types._datetime.now` must pass tz-converted values through `create_datetime_instance`: on Python ≤3.12, pendulum drops a plain `ZoneInfo` on `timedelta` arithmetic
- **`logging.py`** — Log handler reset (autouse)
- **`telemetry.py`** — Instrumentation fixtures
- **`storage.py`** — Local filesystem fixtures
- **`docker.py`** — Docker container helpers
- **`collections_registry.py`** — K8s job template fixtures
- **`deprecation.py`** — Deprecation warning helpers
 
 ## Commonly Used Fixtures

For server tests, the typical fixture chain is:

`session` → `flow` → `flow_run` → `task_run`

Each creates an ORM object in the database and commits. Fixtures like `deployment` depend on `flow`, `work_queue_1`, and `storage_document_id`.

`initialize_orchestration` is the key fixture for testing orchestration rules — it sets up a `FlowOrchestrationContext` or `TaskOrchestrationContext` with configurable initial and proposed states.