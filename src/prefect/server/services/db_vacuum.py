"""
The database vacuum service. Periodically schedules cleanup tasks for old
flow runs and orphaned resources (logs, artifacts, artifact collections)
past a configurable retention period.

A single perpetual service (schedule_vacuum_tasks) enqueues one docket task
per resource type on each cycle. Each task runs independently with its own
error isolation and docket-managed retries. Deterministic keys prevent
duplicate tasks from accumulating if a cycle overlaps with in-progress work.
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
    """Schedule independent cleanup tasks for each resource type.

    Each task is enqueued with a deterministic key so that overlapping
    cycles (e.g. when cleanup takes longer than loop_seconds) naturally
    deduplicate instead of piling up redundant work.
    """
    await docket.add(vacuum_orphaned_logs, key="db-vacuum:orphaned-logs")()
    await docket.add(vacuum_orphaned_artifacts, key="db-vacuum:orphaned-artifacts")()
    await docket.add(
        vacuum_stale_artifact_collections, key="db-vacuum:stale-collections"
    )()
    await docket.add(vacuum_old_flow_runs, key="db-vacuum:old-flow-runs")()


# ---------------------------------------------------------------------------
# Cleanup tasks (docket task functions)
# ---------------------------------------------------------------------------


async def vacuum_orphaned_logs(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Delete logs whose flow_run_id references a non-existent flow run."""
    settings = get_current_settings().server.services.db_vacuum
    orphaned_fk_ids = await _find_orphaned_fk_ids(
        db, db.Log, db.Log.flow_run_id, db.FlowRun
    )
    if not orphaned_fk_ids:
        return
    deleted = await _batch_delete(
        db,
        db.Log,
        db.Log.flow_run_id.in_(orphaned_fk_ids),
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
    orphaned_fk_ids = await _find_orphaned_fk_ids(
        db, db.Artifact, db.Artifact.flow_run_id, db.FlowRun
    )
    if not orphaned_fk_ids:
        return
    deleted = await _batch_delete(
        db,
        db.Artifact,
        db.Artifact.flow_run_id.in_(orphaned_fk_ids),
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _find_orphaned_fk_ids(
    db: PrefectDBInterface,
    child_model: type,
    fk_column: sa.Column,
    parent_model: type,
) -> list:
    """Find foreign key values in child_model that have no matching parent row.

    Queries the distinct set of FK values rather than scanning every child row,
    which allows the database to use an index scan on the FK column instead of
    a full table scan.
    """
    distinct_fks = (
        sa.select(fk_column.label("fk_id"))
        .where(fk_column.is_not(None))
        .distinct()
        .subquery()
    )
    orphaned = sa.select(distinct_fks.c.fk_id).where(
        ~sa.exists(
            sa.select(sa.literal(1)).where(parent_model.id == distinct_fks.c.fk_id)
        )
    )
    async with db.session_context() as session:
        result = await session.execute(orphaned)
        return result.scalars().all()


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
