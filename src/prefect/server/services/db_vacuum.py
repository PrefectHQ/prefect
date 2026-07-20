"""
The database vacuum service. Two perpetual services schedule cleanup tasks
independently, gated by the `enabled` set in
`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` (default `["events"]`):

1. schedule_vacuum_tasks — Cleans up old flow runs and orphaned resources
   (logs, artifacts, artifact collections). Enabled when `"flow_runs"`
   is in the enabled set.

2. schedule_event_vacuum_tasks — Cleans up old events, including any
   event types with per-type retention overrides. Enabled when `"events"`
   is in the enabled set **and** `event_persister.enabled` is true
   (the default), so that operators who disabled event processing are not
   surprised on upgrade. Runs in all server modes, including ephemeral.

Per-event-type retention can be customised via
`PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES`. Event types
not listed fall back to `server.events.retention_period`.

Each task runs independently with its own error isolation and
docket-managed retries. Deterministic keys prevent duplicate tasks from
accumulating if a cycle overlaps with in-progress work.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncIterator

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Perpetual
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.server.schemas.states import TERMINAL_STATES
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now

logger: logging.Logger = get_logger(__name__)


# Vacuum runs batched maintenance deletes that legitimately scan large tables
# (e.g. the orphaned-log anti-join). On Postgres these inherit the asyncpg
# `command_timeout` derived from `PREFECT_API_DATABASE_TIMEOUT` (10s by
# default) — a latency budget meant for user-facing API queries, not bulk
# maintenance. When a batch exceeds it asyncpg raises `TimeoutError`, killing
# the task before it makes progress. Maintenance work runs on a dedicated
# connection with no statement timeout so it can run to completion; sqlite's
# `timeout` is a lock-wait, not a statement deadline, so it is left as-is.
_MAINTENANCE_CONFIGS: dict[str, AsyncPostgresConfiguration] = {}


def _maintenance_database_config(
    db: PrefectDBInterface,
) -> AsyncPostgresConfiguration | None:
    """Return a Postgres config with no statement timeout for vacuum work.

    Returns `None` for non-Postgres backends, signalling callers to use the
    default session.
    """
    config = db.database_config
    if not isinstance(config, AsyncPostgresConfiguration):
        return None
    cached = _MAINTENANCE_CONFIGS.get(config.connection_url)
    if cached is None:
        cached = AsyncPostgresConfiguration(connection_url=config.connection_url)
        # Opt out of the API statement timeout and keep a minimal pool, since
        # vacuum tasks run sequentially on an hourly loop.
        cached.timeout = None
        cached.sqlalchemy_pool_size = 1
        cached.sqlalchemy_max_overflow = 0
        _MAINTENANCE_CONFIGS[config.connection_url] = cached
    return cached


@asynccontextmanager
async def _maintenance_session(
    db: PrefectDBInterface,
) -> AsyncIterator[AsyncSession]:
    """A transactional session for vacuum maintenance queries.

    On Postgres this uses a dedicated connection with no statement timeout;
    other backends fall back to the default session context.
    """
    config = _maintenance_database_config(db)
    if config is None:
        async with db.session_context(begin_transaction=True) as session:
            yield session
        return
    engine = await config.engine()
    session = await config.session(engine)
    async with session:
        async with config.begin_transaction(session):
            yield session


# ---------------------------------------------------------------------------
# Finder (perpetual service)
# ---------------------------------------------------------------------------


@perpetual_service(
    enabled_getter=lambda: (
        "flow_runs"
        in get_current_settings().server.services.db_vacuum.enabled_vacuum_types
    ),
)
async def schedule_vacuum_tasks(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=timedelta(
            seconds=get_current_settings().server.services.db_vacuum.loop_seconds
        ),
    ),
) -> None:
    """Schedule cleanup tasks for old flow runs and orphaned resources.

    Each task is enqueued with a deterministic key so that overlapping
    cycles (e.g. when cleanup takes longer than loop_seconds) naturally
    deduplicate instead of piling up redundant work.

    Disabled by default because it permanently deletes flow runs. Enable
    via PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED=true.
    """
    await docket.add(vacuum_orphaned_logs, key="db-vacuum:orphaned-logs")()
    await docket.add(vacuum_orphaned_artifacts, key="db-vacuum:orphaned-artifacts")()
    await docket.add(
        vacuum_stale_artifact_collections, key="db-vacuum:stale-collections"
    )()
    await docket.add(vacuum_old_flow_runs, key="db-vacuum:old-flow-runs")()


@perpetual_service(
    enabled_getter=lambda: (
        "events"
        in get_current_settings().server.services.db_vacuum.enabled_vacuum_types
        and get_current_settings().server.services.event_persister.enabled
    ),
    run_in_ephemeral=True,
)
async def schedule_event_vacuum_tasks(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=timedelta(
            seconds=get_current_settings().server.services.db_vacuum.loop_seconds
        ),
    ),
) -> None:
    """Schedule cleanup tasks for old events and heartbeat events.

    Enabled by default (`"events"` is in the default enabled set).
    Automatically disabled when the event persister service is disabled
    (PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED=false) so that
    operators who opted out of event processing are not surprised by
    trimming on upgrade.
    """
    await docket.add(
        vacuum_events_with_retention_overrides, key="db-vacuum:retention-overrides"
    )()
    await docket.add(vacuum_old_events, key="db-vacuum:old-events")()


# ---------------------------------------------------------------------------
# Cleanup tasks (docket task functions)
# ---------------------------------------------------------------------------


async def vacuum_orphaned_logs(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete logs whose flow_run_id references a non-existent flow run."""
    settings = get_current_settings().server.services.db_vacuum
    deleted = await _batch_delete(
        db,
        db.Log,
        sa.and_(
            db.Log.flow_run_id.is_not(None),
            ~sa.exists(
                sa.select(sa.literal(1)).where(db.FlowRun.id == db.Log.flow_run_id)
            ),
        ),
        settings.batch_size,
    )
    if deleted:
        logger.info("Database vacuum: deleted %d orphaned logs.", deleted)


async def vacuum_orphaned_artifacts(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete artifacts whose flow_run_id references a non-existent flow run."""
    settings = get_current_settings().server.services.db_vacuum
    deleted = await _batch_delete(
        db,
        db.Artifact,
        sa.and_(
            db.Artifact.flow_run_id.is_not(None),
            ~sa.exists(
                sa.select(sa.literal(1)).where(db.FlowRun.id == db.Artifact.flow_run_id)
            ),
        ),
        settings.batch_size,
    )
    if deleted:
        logger.info("Database vacuum: deleted %d orphaned artifacts.", deleted)


async def vacuum_stale_artifact_collections(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Reconcile artifact collections whose latest_id points to a deleted artifact.

    Re-points to the next latest version if one exists, otherwise deletes
    the collection row.
    """
    settings = get_current_settings().server.services.db_vacuum
    updated, deleted = await _reconcile_artifact_collections(db, settings.batch_size)
    if updated or deleted:
        logger.info(
            "Database vacuum: reconciled %d stale artifact collections "
            "(%d re-pointed, %d removed).",
            updated + deleted,
            updated,
            deleted,
        )


async def vacuum_old_flow_runs(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete old top-level terminal flow runs past the retention period."""
    settings = get_current_settings().server.services.db_vacuum
    retention_cutoff = now("UTC") - settings.retention_period
    deleted = await _batch_delete(
        db,
        db.FlowRun,
        sa.and_(
            db.FlowRun.parent_task_run_id.is_(None),
            db.FlowRun.state_type.in_(TERMINAL_STATES),
            db.FlowRun.end_time.is_not(None),
            db.FlowRun.end_time < retention_cutoff,
        ),
        settings.batch_size,
    )
    if deleted:
        logger.info("Database vacuum: deleted %d old flow runs.", deleted)


async def vacuum_events_with_retention_overrides(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete events whose types have per-type retention overrides.

    Iterates over all entries in `event_retention_overrides` and deletes
    events (and their resources) that are older than the configured retention
    for that type, capped by the global events retention period.
    """
    settings = get_current_settings()
    global_retention = settings.server.events.retention_period
    overrides = settings.server.services.db_vacuum.event_retention_overrides
    batch_size = settings.server.services.db_vacuum.batch_size

    for event_type, type_retention in overrides.items():
        retention = min(type_retention, global_retention)
        retention_cutoff = now("UTC") - retention

        # Delete event resources first (no FK cascade)
        # The subquery finds event IDs matching the event type and age;
        # the outer filter uses EventResource.occurred (already indexed)
        # as a pre-filter and EventResource.event_id (newly indexed) for
        # the join, avoiding the full table scan described in #22535.
        event_ids = (
            sa.select(db.Event.id)
            .where(
                db.Event.event == event_type,
                db.Event.occurred < retention_cutoff,
            )
            .scalar_subquery()
        )
        resources_deleted = await _batch_delete(
            db,
            db.EventResource,
            sa.and_(
                db.EventResource.occurred < retention_cutoff,
                db.EventResource.event_id.in_(event_ids),
            ),
            batch_size,
        )

        # Then delete the events themselves
        events_deleted = await _batch_delete(
            db,
            db.Event,
            sa.and_(
                db.Event.event == event_type,
                db.Event.occurred < retention_cutoff,
            ),
            batch_size,
        )
        if events_deleted or resources_deleted:
            logger.info(
                "Database vacuum: deleted %d %r events and %d event resources.",
                events_deleted,
                event_type,
                resources_deleted,
            )


async def vacuum_old_events(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete all events and event resources past the general events retention period."""
    settings = get_current_settings()
    retention_cutoff = now("UTC") - settings.server.events.retention_period
    batch_size = settings.server.services.db_vacuum.batch_size

    # Delete old event resources first (no FK cascade on event_id).
    # Uses EventResource.occurred (the event timestamp) rather than
    # EventResource.updated (the row insertion time) so that retention
    # is measured from when the event happened, consistent with how
    # events themselves are deleted by Event.occurred below.
    resources_deleted = await _batch_delete(
        db,
        db.EventResource,
        db.EventResource.occurred < retention_cutoff,
        batch_size,
    )

    # Then delete old events
    events_deleted = await _batch_delete(
        db,
        db.Event,
        db.Event.occurred < retention_cutoff,
        batch_size,
    )
    if events_deleted or resources_deleted:
        logger.info(
            "Database vacuum: deleted %d old events and %d event resources.",
            events_deleted,
            resources_deleted,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _reconcile_artifact_collections(
    db: PrefectDBInterface,
    batch_size: int,
) -> tuple[int, int]:
    """Reconcile artifact collections whose latest_id points to a deleted artifact.

    For each stale collection, if another artifact with the same key still
    exists, re-point latest_id to the newest remaining version (mirroring the
    logic in models.artifacts.delete_artifact). Otherwise delete the row.

    Returns (updated_count, deleted_count).
    """
    total_updated = 0
    total_deleted = 0
    stale_condition = ~sa.exists(
        sa.select(sa.literal(1)).where(
            db.Artifact.id == db.ArtifactCollection.latest_id
        )
    )

    while True:
        async with _maintenance_session(db) as session:
            rows = (
                await session.execute(
                    sa.select(db.ArtifactCollection.id, db.ArtifactCollection.key)
                    .where(stale_condition)
                    .limit(batch_size)
                )
            ).all()

            if not rows:
                break

            for collection_id, key in rows:
                next_latest = (
                    await session.execute(
                        sa.select(db.Artifact)
                        .where(db.Artifact.key == key)
                        .order_by(db.Artifact.created.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if next_latest is not None:
                    await session.execute(
                        sa.update(db.ArtifactCollection)
                        .where(db.ArtifactCollection.id == collection_id)
                        .values(
                            latest_id=next_latest.id,
                            data=next_latest.data,
                            description=next_latest.description,
                            type=next_latest.type,
                            created=next_latest.created,
                            updated=next_latest.updated,
                            flow_run_id=next_latest.flow_run_id,
                            task_run_id=next_latest.task_run_id,
                            metadata_=next_latest.metadata_,
                        )
                    )
                    total_updated += 1
                else:
                    await session.execute(
                        sa.delete(db.ArtifactCollection).where(
                            db.ArtifactCollection.id == collection_id
                        )
                    )
                    total_deleted += 1

        await asyncio.sleep(0)

    return total_updated, total_deleted


async def _batch_delete(
    db: PrefectDBInterface,
    model: type,
    condition: sa.ColumnElement[bool],
    batch_size: int,
) -> int:
    """Delete matching rows in batches. Each batch gets its own DB transaction."""
    total = 0
    while True:
        async with _maintenance_session(db) as session:
            subquery = (
                sa.select(model.id).where(condition).limit(batch_size).scalar_subquery()
            )
            result = await session.execute(
                sa.delete(model).where(model.id.in_(subquery))
            )
            deleted = result.rowcount
        if deleted == 0:
            break
        total += deleted
        await asyncio.sleep(0)  # yield to event loop between batches
    return total
