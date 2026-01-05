"""
The Foreman service. Monitors workers and marks stale resources as offline/not ready.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import sqlalchemy as sa
from docket import Perpetual

from prefect.logging import get_logger
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

logger: logging.Logger = get_logger(__name__)


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.foreman.enabled,
)
async def monitor_worker_health(
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.foreman.loop_seconds
        ),
    ),
) -> None:
    """
    Monitor workers and mark stale resources as offline/not ready.

    Iterates over workers currently marked as online. Marks workers as offline
    if they have an old last_heartbeat_time. Marks work pools as not ready
    if they do not have any online workers and are currently marked as ready.
    Marks deployments as not ready if they have a last_polled time that is
    older than the configured deployment last polled timeout.
    """
    settings = get_current_settings().server.services.foreman
    db = provide_database_interface()

    await _mark_online_workers_without_recent_heartbeat_as_offline(
        db=db,
        inactivity_heartbeat_multiple=settings.inactivity_heartbeat_multiple,
        fallback_heartbeat_interval_seconds=settings.fallback_heartbeat_interval_seconds,
    )
    await _mark_work_pools_as_not_ready(db=db)
    await _mark_deployments_as_not_ready(
        db=db,
        deployment_last_polled_timeout_seconds=settings.deployment_last_polled_timeout_seconds,
    )
    await _mark_work_queues_as_not_ready(
        db=db,
        work_queue_last_polled_timeout_seconds=settings.work_queue_last_polled_timeout_seconds,
    )


async def _mark_online_workers_without_recent_heartbeat_as_offline(
    db: PrefectDBInterface,
    inactivity_heartbeat_multiple: int,
    fallback_heartbeat_interval_seconds: int,
) -> None:
    """
    Updates the status of workers that have an old last heartbeat time to OFFLINE.

    An old heartbeat is one that is more than the worker's heartbeat interval
    multiplied by the inactivity_heartbeat_multiple seconds ago.
    """
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

    if result.rowcount:
        logger.info(f"Marked {result.rowcount} workers as offline.")


async def _mark_work_pools_as_not_ready(db: PrefectDBInterface) -> None:
    """
    Marks work pools as not ready if they have no online workers.

    Emits an event and updates any bookkeeping fields on the work pool.
    """
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

            logger.info(f"Marked work pool {work_pool.id} as NOT_READY.")


async def _mark_deployments_as_not_ready(
    db: PrefectDBInterface,
    deployment_last_polled_timeout_seconds: int,
) -> None:
    """
    Marks deployments as NOT_READY based on their last_polled field.

    Emits an event and updates any bookkeeping fields on the deployment.
    """
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


async def _mark_work_queues_as_not_ready(
    db: PrefectDBInterface,
    work_queue_last_polled_timeout_seconds: int,
) -> None:
    """
    Marks work queues as NOT_READY based on their last_polled field.
    """
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
