"""
The Scheduler service.
"""

import asyncio
import datetime
from typing import Dict, List
from uuid import UUID

import pendulum
import sqlalchemy as sa

import prefect.orion.models as models
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.services.loop_service import LoopService
from prefect.settings import (
    PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
)
from prefect.utilities.collections import batched_iterable


class Scheduler(LoopService):
    """
    A loop service that schedules flow runs from deployments.
    """

    def __init__(self, loop_seconds: float = None):
        super().__init__(
            loop_seconds or PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS.value()
        )
        self.deployment_batch_size: int = (
            PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE.value()
        )
        self.max_runs: int = PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value()
        self.max_scheduled_time: datetime.timedelta = (
            PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
        )
        self.insert_batch_size = (
            PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
        )

    @inject_db
    async def run_once(self, db: OrionDBInterface):
        """
        Schedule flow runs by:

        - Querying for deployments with active schedules
        - Generating the next set of flow runs based on each deployments schedule
        - Inserting all scheduled flow runs into the database

        All inserted flow runs are committed to the database at the termination of the loop.
        """
        now = pendulum.now("UTC")
        total_inserted_runs = 0

        session = await db.session()
        async with session:
            last_id = None
            while True:
                async with session.begin():
                    query = self._get_select_deployments_to_schedule_query()

                    # use cursor based pagination
                    if last_id:
                        query = query.where(db.Deployment.id > last_id)

                    result = await session.execute(query)
                    deployment_ids = result.scalars().unique().all()

                    # collect runs across all deployments
                    runs_to_insert = []
                    for deployment_id in deployment_ids:
                        # guard against erroneously configured schedules
                        try:
                            runs_to_insert.extend(
                                await self._generate_scheduled_flow_runs(
                                    session=session,
                                    deployment_id=deployment_id,
                                    start_time=now,
                                    end_time=now + self.max_scheduled_time,
                                    max_runs=self.max_runs,
                                )
                            )
                        except Exception as exc:
                            self.logger.error(
                                f"Error scheduling deployment {deployment_id!r}.",
                                exc_info=True,
                            )

                    # bulk insert the runs based on batch size setting
                    for batch in batched_iterable(
                        runs_to_insert, self.insert_batch_size
                    ):
                        inserted_runs = await self._insert_scheduled_flow_runs(
                            session=session, runs=batch
                        )
                        total_inserted_runs += len(inserted_runs)

                # if no deployments were found, exit the loop
                if len(deployment_ids) < self.deployment_batch_size:
                    break
                else:
                    # record the last deployment ID
                    last_id = deployment_ids[-1]

            self.logger.info(f"Scheduled {total_inserted_runs} runs.")

    @inject_db
    def _get_select_deployments_to_schedule_query(self, db: OrionDBInterface):
        """
        Returns a sqlalchemy query for selecting deployments to schedule
        """
        query = (
            sa.select(db.Deployment.id)
            .where(
                db.Deployment.is_schedule_active.is_(True),
                db.Deployment.schedule.is_not(None),
            )
            .order_by(db.Deployment.id)
            .limit(self.deployment_batch_size)
        )
        return query

    @inject_db
    async def _generate_scheduled_flow_runs(
        self,
        session: sa.orm.Session,
        deployment_id: UUID,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        max_runs: int,
        db: OrionDBInterface,
    ) -> List[Dict]:
        """
        Given a `deployment_id` and schedule params, generates a list of flow run objects and
        associated scheduled states that represent scheduled flow runs.

        Pass-through method for overrides.
        """
        return await models.deployments._generate_scheduled_flow_runs(
            session=session,
            deployment_id=deployment_id,
            start_time=start_time,
            end_time=end_time,
            max_runs=max_runs,
        )

    @inject_db
    async def _insert_scheduled_flow_runs(
        self,
        session: sa.orm.Session,
        runs: List[Dict],
        db: OrionDBInterface,
    ) -> List[UUID]:
        """
        Given a list of flow runs to schedule, as generated by `_generate_scheduled_flow_runs`,
        inserts them into the database. Note this is a separate method to facilitate batch
        operations on many scheduled runs.

        Pass-through method for overrides.
        """
        return await models.deployments._insert_scheduled_flow_runs(
            session=session, runs=runs
        )


if __name__ == "__main__":
    asyncio.run(Scheduler().start())
