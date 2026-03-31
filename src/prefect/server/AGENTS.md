# Prefect Server

Orchestration backend managing flow runs, scheduling, and state tracking. This is the source of truth for all state transitions.

## Key Contracts

- **All state changes go through the orchestration layer** — never bypass it, even in tests
- **SQLite and PostgreSQL must be kept in lockstep** — every migration, every query. Some queries need database-specific variants where SQLite lacks PostgreSQL features. CI tests both databases.
- **Server and client code should not mix** — the server has its own schemas (`server/schemas/`) separate from client schemas (`client/schemas/`). Keep the boundary clean.
- **Auth token comparisons must use `hmac.compare_digest`** — never compare auth tokens with `==` or `!=`. Direct equality checks are vulnerable to timing attacks that can leak secrets. Applies to CSRF tokens (`api/middleware.py`), HTTP basic auth (`api/server.py`), and WebSocket auth (`utilities/subscriptions.py`).
- **Use `SizedParameters` for action schema `parameters` fields** — `schemas/actions.py` defines `SizedParameters = Annotated[Dict[str, Any], AfterValidator(validate_parameter_size_field)]`. Any action model that accepts flow run or deployment parameters must use this type instead of `Dict[str, Any]`. It enforces the `PREFECT_SERVER_API_MAX_PARAMETER_SIZE` limit (default 512 KB, set to 0 to disable) and returns a 422 on violation.

## Adding a New API Endpoint

Follow this layering order:

1. **Schema** (`schemas/`) — Define Pydantic request/response models
2. **Model** (`models/`) — Add SQLAlchemy ORM operations
3. **Route** (`api/`) — Wire up the FastAPI endpoint

The `variables` endpoints are a good canonical example of this pattern for simple CRUD.

## Database Migrations

Migrations use Alembic via wrapper functions in `database/alembic_commands.py`:

```python
from prefect.server.database.alembic_commands import alembic_upgrade, alembic_downgrade, alembic_revision

alembic_upgrade("head")              # Apply all pending migrations
alembic_downgrade("-1")              # Roll back one migration
alembic_revision("description")      # Create a new migration
```

**Every migration must support both SQLite and PostgreSQL.** Migration scripts live in `database/_migrations/`. Config is in `database/alembic.ini`.

## Orchestration Pitfalls

- **Pydantic v2 treats null JSON fields as explicitly set.** When a worker sends a state update with `field: null`, Pydantic v2 sets that field to `None`, silently overwriting any existing value. To preserve `state_details` fields across transitions (e.g. `deployment_concurrency_lease_id`), add a `FlowRunUniversalTransform` to `CoreFlowPolicy` that copies the field forward when the proposed state has `None`. See `PreserveDeploymentConcurrencyLeaseId` in `orchestration/core_policy.py` as the canonical pattern. Any new field added to `state_details` that workers may omit faces this same risk.

## Main Subsystems

- `api/` — FastAPI REST endpoints
- `database/` — Connections, ORM models, and Alembic migrations
- `orchestration/` — State transition rules and policies
- `services/` — Background services (scheduler, event services, task queue)
- `events/` — Server-side event processing: trigger evaluation, action execution, messaging, streaming (see also `../events/` for client-side schemas)
- `concurrency/` — Server-side concurrency management
- `logs/` — Log storage and retrieval

## Related

- `../client/` → HTTP client that talks to these endpoints (see client/AGENTS.md)
- `../events/` → Client-side event schemas and emission (see events/AGENTS.md)
- `tests/server/` → Server tests use a stripped-down client; do not mix with full client fixtures
