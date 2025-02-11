"""
Foreman is a loop service designed to monitor workers.
"""

from datetime import timedelta
from typing import Any, Optional

import sqlalchemy as sa

from prefect.server import models
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.models.deployments import mark_deployments_not_ready
from prefect.server.models.work_queues import mark_work_queues_not_ready
from prefect.server.models.workers import emit_work_pool_status_event
from prefect.server.schemas.internal import InternalWorkPoolUpdate
from prefect.server.schemas.statuses import (
    DeploymentStatus,
    WorkerStatus,
    WorkPoolStatus,
)
from prefect.server.services.base import LoopService
from prefect.settings import (
    PREFECT_API_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE,
    PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS,
    get_current_settings,
)
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now


class Foreman(LoopService):
    """
    Monitors the status of workers and their associated work pools
    """

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.foreman

    def __init__(
        self,
        loop_seconds: Optional[float] = None,
        inactivity_heartbeat_multiple: Optional[int] = None,
        fallback_heartbeat_interval_seconds: Optional[int] = None,
        deployment_last_polled_timeout_seconds: Optional[int] = None,
        work_queue_last_polled_timeout_seconds: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS.value(),
            **kwargs,
        )
        self._inactivity_heartbeat_multiple = (
            PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE.value()
            if inactivity_heartbeat_multiple is None
            else inactivity_heartbeat_multiple
        )
        self._fallback_heartbeat_interval_seconds = (
            PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS.value()
            if fallback_heartbeat_interval_seconds is None
            else fallback_heartbeat_interval_seconds
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
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        Iterate over workers current marked as online. Mark workers as offline
        if they have an old last_heartbeat_time. Marks work pools as not ready
        if they do not have any online workers and are currently marked as ready.
        Mark deployments as not ready if they have a last_polled time that is
        older than the configured deployment last polled timeout.
        """
        await self._mark_online_workers_without_a_recent_heartbeat_as_offline()
        await self._mark_work_pools_as_not_ready()
        await self._mark_deployments_as_not_ready()
        await self._mark_work_queues_as_not_ready()

    @db_injector
    async def _mark_online_workers_without_a_recent_heartbeat_as_offline(
        self, db: PrefectDBInterface
    ) -> None:
        """
        Updates the status of workers that have an old last heartbeat time
        to OFFLINE.

        An old heartbeat last heartbeat that is one more than
        their heartbeat interval multiplied by the
        INACTIVITY_HEARTBEAT_MULTIPLE seconds ago.

        Args:
            session (AsyncSession): The session to use for the database operation.
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
                    "multiplier": self._inactivity_heartbeat_multiple,
                    "default_interval": self._fallback_heartbeat_interval_seconds,
                },
            )

        if result.rowcount:
            self.logger.info(f"Marked {result.rowcount} workers as offline.")

    @db_injector
    async def _mark_work_pools_as_not_ready(self, db: PrefectDBInterface):
        """
        Marks a work pool as not ready.

        Emits and event and updates any bookkeeping fields on the work pool.

        Args:
            work_pool (db.WorkPool): The work pool to mark as not ready.
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

                self.logger.info(f"Marked work pool {work_pool.id} as NOT_READY.")

    @db_injector
    async def _mark_deployments_as_not_ready(self, db: PrefectDBInterface) -> None:
        """
        Marks a deployment as NOT_READY and emits a deployment status event.
        Emits an event and updates any bookkeeping fields on the deployment.
        Args:
            session (AsyncSession): The session to use for the database operation.
        """
        async with db.session_context(begin_transaction=True) as session:
            status_timeout_threshold = now("UTC") - timedelta(
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
    async def _mark_work_queues_as_not_ready(self, db: PrefectDBInterface):
        """
        Marks work queues as NOT_READY based on their last_polled field.

        Args:
            session (AsyncSession): The session to use for the database operation.
        """
        async with db.session_context(begin_transaction=True) as session:
            status_timeout_threshold = now("UTC") - timedelta(
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
