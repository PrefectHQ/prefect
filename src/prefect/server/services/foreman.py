"""
Foreman is a loop service designed to monitor workers.
"""

from datetime import timedelta
from typing import Optional

import pendulum
import sqlalchemy as sa
from typing_extensions import Self

from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.models.deployments import mark_deployments_not_ready
from prefect.server.models.work_queues import mark_work_queues_not_ready
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.server.services.loop_service import LoopService
from prefect.settings import (
    PREFECT_API_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS,
)


class Foreman(LoopService):
    """
    A loop service responsible for monitoring the status of workers.

    Handles updating the status of workers and their associated work pools.
    """

    def __init__(
        self,
        loop_seconds: Optional[float] = None,
        deployment_last_polled_timeout_seconds: Optional[int] = None,
        work_queue_last_polled_timeout_seconds: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS.value(),
            **kwargs,
        )
        self._deployment_last_polled_timeout_seconds = (
            PREFECT_API_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS.value()
            if deployment_last_polled_timeout_seconds is None
            else deployment_last_polled_timeout_seconds
        )
        self._work_queue_last_polled_timeout_seconds = (
            PREFECT_API_SERVICES_FOREMAN_WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS.value()
            if work_queue_last_polled_timeout_seconds is None
            else work_queue_last_polled_timeout_seconds
        )

    @db_injector
    async def run_once(db: PrefectDBInterface, self: Self) -> None:
        """
        Iterate over workers current marked as online. Mark workers as offline
        if they have an old last_heartbeat_time. Marks work pools as not ready
        if they do not have any online workers and are currently marked as ready.
        Mark deployments as not ready if they have a last_polled time that is
        older than the configured deployment last polled timeout.
        """
        await self._mark_deployments_as_not_ready()
        await self._mark_work_queues_as_not_ready()

    @db_injector
    async def _mark_deployments_as_not_ready(
        db: PrefectDBInterface,
        self: Self,
    ):
        """
        Marks a deployment as NOT_READY and emits a deployment status event.
        Emits an event and updates any bookkeeping fields on the deployment.
        Args:
            session (AsyncSession): The session to use for the database operation.
        """
        async with db.session_context(begin_transaction=True) as session:
            status_timeout_threshold = pendulum.now("UTC") - timedelta(
                seconds=self._deployment_last_polled_timeout_seconds
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

    @db_injector
    async def _mark_work_queues_as_not_ready(
        db: PrefectDBInterface,
        self: Self,
    ):
        """
        Marks work queues as NOT_READY based on their last_polled field.

        Args:
            session (AsyncSession): The session to use for the database operation.
        """
        async with db.session_context(begin_transaction=True) as session:
            status_timeout_threshold = pendulum.now("UTC") - timedelta(
                seconds=self._work_queue_last_polled_timeout_seconds
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
