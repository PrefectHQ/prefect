"""
The database vacuum service. Two perpetual services schedule cleanup tasks
independently:

1. schedule_vacuum_tasks — Cleans up old flow runs and orphaned resources
   (logs, artifacts, artifact collections). Disabled by default because it
   permanently deletes flow run data. Controlled by
   PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED.

2. schedule_event_vacuum_tasks — Cleans up old events and heartbeat events.
   Enabled by default, replacing EventPersister.trim(). Controlled by
   PREFECT_SERVER_SERVICES_DB_VACUUM_EVENTS_ENABLED.

Each task runs independently with its own error isolation and
docket-managed retries. Deterministic keys prevent duplicate tasks from
accumulating if a cycle overlaps with in-progress work.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Perpetual

from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.states import TERMINAL_STATES
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now

logger: logging.Logger = get_logger(__name__)

HEARTBEAT_EVENT = "prefect.flow-run.heartbeat"


# ---------------------------------------------------------------------------
# Finder (perpetual service)
# ---------------------------------------------------------------------------


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.db_vacuum.enabled,
)
async def schedule_vacuum_tasks(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=False,
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
    enabled_getter=lambda: get_current_settings().server.services.db_vacuum.events_enabled,
)
async def schedule_event_vacuum_tasks(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.db_vacuum.events_loop_seconds
        ),
    ),
) -> None:
    """Schedule cleanup tasks for old events and heartbeat events.

    Enabled by default, replacing the previous EventPersister.trim()
    behavior. Control via PREFECT_SERVER_SERVICES_DB_VACUUM_EVENTS_ENABLED.
    """
    await docket.add(vacuum_heartbeat_events, key="db-vacuum:heartbeat-events")()
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
    existing_flow_run = sa.select(sa.literal(1)).where(
        db.FlowRun.id == db.Log.flow_run_id
    )
    deleted = await _batch_delete(
        db,
        db.Log,
        sa.and_(
            db.Log.flow_run_id.is_not(None),
            ~sa.exists(existing_flow_run),
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
    existing_flow_run = sa.select(sa.literal(1)).where(
        db.FlowRun.id == db.Artifact.flow_run_id
    )
    deleted = await _batch_delete(
        db,
        db.Artifact,
        sa.and_(
            db.Artifact.flow_run_id.is_not(None),
            ~sa.exists(existing_flow_run),
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


async def vacuum_heartbeat_events(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete heartbeat events and their resources past the heartbeat retention period."""
    settings = get_current_settings()
    # Use the shorter of heartbeat retention and general event retention so
    # that heartbeats never outlive a user-configured PREFECT_EVENTS_RETENTION_PERIOD.
    retention = min(
        settings.server.services.db_vacuum.heartbeat_events_retention_period,
        settings.server.events.retention_period,
    )
    retention_cutoff = now("UTC") - retention
    batch_size = settings.server.services.db_vacuum.events_batch_size

    # Delete event resources for old heartbeat events first (no FK cascade)
    heartbeat_event_ids = (
        sa.select(db.Event.id)
        .where(
            db.Event.event == HEARTBEAT_EVENT,
            db.Event.occurred < retention_cutoff,
        )
        .scalar_subquery()
    )
    resources_deleted = await _batch_delete(
        db,
        db.EventResource,
        db.EventResource.event_id.in_(heartbeat_event_ids),
        batch_size,
    )

    # Then delete the heartbeat events themselves
    events_deleted = await _batch_delete(
        db,
        db.Event,
        sa.and_(
            db.Event.event == HEARTBEAT_EVENT,
            db.Event.occurred < retention_cutoff,
        ),
        batch_size,
    )
    if events_deleted or resources_deleted:
        logger.info(
            "Database vacuum: deleted %d heartbeat events and %d event resources.",
            events_deleted,
            resources_deleted,
        )


async def vacuum_old_events(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete all events and event resources past the general events retention period."""
    settings = get_current_settings()
    retention_cutoff = now("UTC") - settings.server.events.retention_period
    batch_size = settings.server.services.db_vacuum.events_batch_size

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
        async with db.session_context(begin_transaction=True) as session:
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
        async with db.session_context(begin_transaction=True) as session:
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
