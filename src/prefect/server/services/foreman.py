"""
Foreman is a loop service designed to monitor workers.
"""

from datetime import timedelta

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Perpetual

from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models.deployments import mark_deployments_not_ready
from prefect.server.models.work_queues import mark_work_queues_not_ready
from prefect.server.models.workers import emit_work_pool_status_event
from prefect.server.schemas.internal import InternalWorkPoolUpdate
from prefect.server.schemas.statuses import (
    DeploymentStatus,
    WorkerStatus,
    WorkPoolStatus,
)
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now


# Docket task function for marking workers offline
async def mark_workers_offline(
    inactivity_heartbeat_multiple: int,
    fallback_heartbeat_interval_seconds: int,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    """Mark workers without recent heartbeat as offline (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        worker_update_stmt = (
            sa.update(db.Worker)
            .values(status=WorkerStatus.OFFLINE)
            .where(
                sa.func.date_diff_seconds(db.Worker.last_heartbeat_time)
                > (
                    sa.func.coalesce(
                        db.Worker.heartbeat_interval_seconds,
                        sa.bindparam("default_interval", sa.Integer),
                    )
                    * sa.bindparam("multiplier", sa.Integer)
                ),
                db.Worker.status == WorkerStatus.ONLINE,
            )
        )

        result = await session.execute(
            worker_update_stmt,
            {
                "multiplier": inactivity_heartbeat_multiple,
                "default_interval": fallback_heartbeat_interval_seconds,
            },
        )

    return result.rowcount


# Docket task function for marking work pools not ready
async def mark_work_pools_not_ready(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark work pools with no online workers as not ready (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        work_pools_select_stmt = (
            sa.select(db.WorkPool)
            .filter(db.WorkPool.status == "READY")
            .outerjoin(
                db.Worker,
                sa.and_(
                    db.Worker.work_pool_id == db.WorkPool.id,
                    db.Worker.status == "ONLINE",
                ),
            )
            .group_by(db.WorkPool.id)
            .having(sa.func.count(db.Worker.id) == 0)
        )

        result = await session.execute(work_pools_select_stmt)
        work_pools = result.scalars().all()

        for work_pool in work_pools:
            await models.workers.update_work_pool(
                session=session,
                work_pool_id=work_pool.id,
                work_pool=InternalWorkPoolUpdate(status=WorkPoolStatus.NOT_READY),
                emit_status_change=emit_work_pool_status_event,
            )


# Docket task function for marking deployments not ready
async def mark_deployments_not_ready_task(
    deployment_last_polled_timeout_seconds: int,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark deployments with old last_polled as not ready (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        status_timeout_threshold = now("UTC") - timedelta(
            seconds=deployment_last_polled_timeout_seconds
        )
        deployment_id_select_stmt = (
            sa.select(db.Deployment.id)
            .outerjoin(db.WorkQueue, db.WorkQueue.id == db.Deployment.work_queue_id)
            .filter(db.Deployment.status == DeploymentStatus.READY)
            .filter(db.Deployment.last_polled.isnot(None))
            .filter(
                sa.or_(
                    # if work_queue.last_polled doesn't exist, use only deployment's
                    # last_polled
                    sa.and_(
                        db.WorkQueue.last_polled.is_(None),
                        db.Deployment.last_polled < status_timeout_threshold,
                    ),
                    # if work_queue.last_polled exists, both times should be less than
                    # the threshold
                    sa.and_(
                        db.WorkQueue.last_polled.isnot(None),
                        db.Deployment.last_polled < status_timeout_threshold,
                        db.WorkQueue.last_polled < status_timeout_threshold,
                    ),
                )
            )
        )
        result = await session.execute(deployment_id_select_stmt)
        deployment_ids_to_mark_unready = result.scalars().all()

    await mark_deployments_not_ready(
        deployment_ids=deployment_ids_to_mark_unready,
    )


# Docket task function for marking work queues not ready
async def mark_work_queues_not_ready_task(
    work_queue_last_polled_timeout_seconds: int,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark work queues with old last_polled as not ready (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        status_timeout_threshold = now("UTC") - timedelta(
            seconds=work_queue_last_polled_timeout_seconds
        )
        id_select_stmt = (
            sa.select(db.WorkQueue.id)
            .outerjoin(db.WorkPool, db.WorkPool.id == db.WorkQueue.work_pool_id)
            .filter(db.WorkQueue.status == "READY")
            .filter(db.WorkQueue.last_polled.isnot(None))
            .filter(db.WorkQueue.last_polled < status_timeout_threshold)
            .order_by(db.WorkQueue.last_polled.asc())
        )
        result = await session.execute(id_select_stmt)
        unready_work_queue_ids = result.scalars().all()

    await mark_work_queues_not_ready(
        work_queue_ids=unready_work_queue_ids,
    )


# Perpetual monitor for worker/work pool health (find and flood pattern)
@perpetual_service(
    settings_getter=lambda: get_current_settings().server.services.foreman,
)
async def monitor_worker_health(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.foreman.loop_seconds
        ),
    ),
) -> None:
    """Monitor worker and work pool health, scheduling monitoring tasks."""

    settings = get_current_settings().server.services.foreman

    # Schedule all foreman monitoring tasks
    await docket.add(mark_workers_offline)(
        settings.inactivity_heartbeat_multiple,
        settings.fallback_heartbeat_interval_seconds,
    )
    await docket.add(mark_work_pools_not_ready)()
    await docket.add(mark_deployments_not_ready_task)(
        settings.deployment_last_polled_timeout_seconds,
    )
    await docket.add(mark_work_queues_not_ready_task)(
        settings.work_queue_last_polled_timeout_seconds,
    )
