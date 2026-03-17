# Prefect Server

Orchestration backend managing flow runs, scheduling, and state tracking. This is the source of truth for all state transitions.

## Key Contracts

- **All state changes go through the orchestration layer** — never bypass it, even in tests
- **SQLite and PostgreSQL must be kept in lockstep** — every migration, every query. Some queries need database-specific variants where SQLite lacks PostgreSQL features. CI tests both databases.
- **Server and client code should not mix** — the server has its own schemas (`server/schemas/`) separate from client schemas (`client/schemas/`). Keep the boundary clean.
- **Auth token comparisons must use `hmac.compare_digest`** — never compare auth tokens with `==` or `!=`. Direct equality checks are vulnerable to timing attacks that can leak secrets. Applies to CSRF tokens (`api/middleware.py`), HTTP basic auth (`api/server.py`), and WebSocket auth (`utilities/subscriptions.py`).
- **Deployment delete events must be built before the DELETE executes** — `models/deployments.py` emits `prefect.deployment.created/updated/deleted` lifecycle events. For deletes specifically, the event payload is constructed while the ORM object is still in-session; building it after the `DELETE` will silently produce no event because the deployment is gone. Only fields listed in `DEPLOYMENT_EVENT_FIELDS` trigger `updated` events.

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
