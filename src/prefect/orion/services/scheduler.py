"""
The Scheduler service.
"""

import datetime
import asyncio
from uuid import UUID
from typing import Dict, List

import pendulum
import sqlalchemy as sa

import prefect
from prefect.orion import models, schemas
from prefect.orion.services.loop_service import LoopService
from prefect.utilities.collections import batched_iterable
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface

settings = prefect.settings.orion.services


class Scheduler(LoopService):
    """
    A loop service that schedules flow runs from deployments.
    """

    loop_seconds: float = settings.scheduler_loop_seconds
    deployment_batch_size: int = settings.scheduler_deployment_batch_size
    max_runs: int = settings.scheduler_max_runs
    max_scheduled_time: datetime.timedelta = settings.scheduler_max_scheduled_time

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
            async with session.begin():
                last_id = None
                while True:
                    query = self._get_select_deployments_to_schedule_query()

                    # use cursor based pagination
                    if last_id:
                        query = query.where(db.Deployment.id > last_id)

                    result = await session.execute(query)
                    deployment_ids = result.scalars().unique().all()

                    # collect runs across all deployments
                    all_runs = []
                    for deployment_id in deployment_ids:
                        runs = await self._generate_scheduled_flow_runs(
                            session=session,
                            deployment_id=deployment_id,
                            start_time=now,
                            end_time=now + self.max_scheduled_time,
                            max_runs=self.max_runs,
                        )
                        all_runs.extend(runs)

                    # bulk insert the runs based on batch size setting
                    for batch in batched_iterable(
                        all_runs, settings.scheduler_insert_batch_size
                    ):
                        inserted_runs = await self._insert_scheduled_flow_runs(
                            session=session, runs=batch
                        )
                        await session.flush()
                        total_inserted_runs += len(inserted_runs)

                    # if no deployments were found, exit the loop
                    if len(deployment_ids) < self.deployment_batch_size:
                        break
                    else:
                        # record the last deployment ID
                        last_id = deployment_ids[-1].id

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
        Given a `deployment_id` and schedule, generates a list of flow run objects and
        associated scheduled states that represent scheduled flow runs.

        This method does NOT insert generated runs into the database.

        Args:
            session: a database session
            deployment_id: the id of the deployment to schedule
            start_time: the time from which to start scheduling runs
            end_time: a limit on how far in the future runs will be scheduled
            max_runs: a maximum amount of runs to schedule

        Returns:
            a list of dictionaries representing flow runs to schedule for
                the deployment specified
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

        Args:
            session: a database session
            runs: a list of dictionaries representing flow runs to insert

        Returns a list of flow run ids that were inserted
        """
        return await models.deployments._insert_scheduled_flow_runs(
            session=session, runs=runs
        )


if __name__ == "__main__":
    asyncio.run(Scheduler().start())
