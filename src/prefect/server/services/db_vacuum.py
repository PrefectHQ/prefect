"""
The database vacuum service. Periodically deletes old flow runs and
orphaned resources (logs, artifacts, artifact collections) past a
configurable retention period.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import sqlalchemy as sa
from docket import Perpetual

from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.states import TERMINAL_STATES
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now

logger: logging.Logger = get_logger(__name__)


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.db_vacuum.enabled,
)
async def vacuum_old_resources(
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.db_vacuum.loop_seconds
        ),
    ),
) -> None:
    """
    Delete old flow runs and orphaned resources past the retention period.

    Deletion order (orphans first, then flow runs):
    1. Orphaned logs — logs whose flow_run_id points to a deleted flow run
    2. Orphaned artifacts — same pattern as logs
    3. Stale artifact collections — collections whose latest_id points to a
       deleted artifact
    4. Old top-level flow runs — terminal flow runs older than retention_period

    Orphans are cleaned first so that leftovers from a previous interrupted
    cycle are handled before creating new orphans in step 4.
    """
    settings = get_current_settings().server.services.db_vacuum
    db = provide_database_interface()
    retention_cutoff = now("UTC") - settings.retention_period
    batch_size = settings.batch_size

    logs_deleted = 0
    artifacts_deleted = 0
    collections_updated = 0
    collections_deleted = 0
    flow_runs_deleted = 0

    # Each step is isolated so that a failure in one does not skip the rest.

    # 1. Orphaned logs
    try:
        existing_flow_run_for_log = sa.select(sa.literal(1)).where(
            db.FlowRun.id == db.Log.flow_run_id
        )
        logs_deleted = await _batch_delete(
            db,
            db.Log,
            sa.and_(
                db.Log.flow_run_id.is_not(None),
                ~sa.exists(existing_flow_run_for_log),
            ),
            batch_size,
        )
    except Exception:
        logger.exception("Database vacuum: failed to clean orphaned logs.")

    # 2. Orphaned artifacts
    try:
        existing_flow_run_for_artifact = sa.select(sa.literal(1)).where(
            db.FlowRun.id == db.Artifact.flow_run_id
        )
        artifacts_deleted = await _batch_delete(
            db,
            db.Artifact,
            sa.and_(
                db.Artifact.flow_run_id.is_not(None),
                ~sa.exists(existing_flow_run_for_artifact),
            ),
            batch_size,
        )
    except Exception:
        logger.exception("Database vacuum: failed to clean orphaned artifacts.")

    # 3. Stale artifact collections — re-point to next latest version if one
    #    exists, otherwise delete the collection row.
    try:
        collections_updated, collections_deleted = (
            await _reconcile_artifact_collections(db, batch_size)
        )
    except Exception:
        logger.exception(
            "Database vacuum: failed to reconcile artifact collections."
        )

    # 4. Old top-level flow runs
    try:
        flow_runs_deleted = await _batch_delete(
            db,
            db.FlowRun,
            sa.and_(
                db.FlowRun.parent_task_run_id.is_(None),
                db.FlowRun.state_type.in_(TERMINAL_STATES),
                db.FlowRun.end_time.is_not(None),
                db.FlowRun.end_time < retention_cutoff,
            ),
            batch_size,
        )
    except Exception:
        logger.exception("Database vacuum: failed to clean old flow runs.")

    total = (
        logs_deleted
        + artifacts_deleted
        + collections_updated
        + collections_deleted
        + flow_runs_deleted
    )
    if total > 0:
        logger.info(
            "Database vacuum completed: deleted %d flow runs, %d orphaned logs, "
            "%d orphaned artifacts, %d stale artifact collections "
            "(%d re-pointed, %d removed).",
            flow_runs_deleted,
            logs_deleted,
            artifacts_deleted,
            collections_updated + collections_deleted,
            collections_updated,
            collections_deleted,
        )
    else:
        logger.debug("Database vacuum completed: nothing to delete.")


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
                        sa.delete(db.ArtifactCollection)
                        .where(db.ArtifactCollection.id == collection_id)
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
