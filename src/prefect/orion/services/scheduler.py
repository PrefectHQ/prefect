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
from prefect.orion.services.loop_service import LoopService, run_multiple_services
from prefect.settings import (
    PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
)
from prefect.utilities.collections import batched_iterable


class TryAgain(Exception):
    """Internal control-flow exception used to retry the Scheduler's main loop"""


class Scheduler(LoopService):
    """
    A loop service that schedules flow runs from deployments.
    """

    # the main scheduler takes its loop interval from
    # PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS
    loop_seconds = None

    def __init__(self, loop_seconds: float = None, **kwargs):
        super().__init__(
            loop_seconds=(
                loop_seconds
                or self.loop_seconds
                or PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS.value()
            ),
            **kwargs,
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

        All inserted flow runs are committed to the database at the termination of the
        loop.
        """
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
                    try:
                        runs_to_insert = await self._collect_flow_runs(
                            session=session, deployment_ids=deployment_ids
                        )
                    except TryAgain:
                        continue

                    # bulk insert the runs based on batch size setting
                    for batch in batched_iterable(
                        runs_to_insert, self.insert_batch_size
                    ):
                        inserted_runs = await self._insert_scheduled_flow_runs(
                            session=session, runs=batch
                        )
                        total_inserted_runs += len(inserted_runs)

                # if this is the last page of deployments, exit the loop
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

    async def _collect_flow_runs(
        self,
        session: sa.orm.Session,
        deployment_ids: List[UUID],
    ) -> List[Dict]:
        runs_to_insert = []
        for deployment_id in deployment_ids:
            now = pendulum.now("UTC")
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
            except Exception:
                self.logger.exception(
                    f"Error scheduling deployment {deployment_id!r}.",
                )
            finally:
                connection = await session.connection()
                if connection.invalidated:
                    # If the error we handled above was the kind of database error that
                    # causes underlying transaction to rollback and the connection to
                    # become invalidated, rollback this session.  Errors that may cause
                    # this are connection drops, database restarts, and things of the
                    # sort.
                    #
                    # This rollback _does not rollback a transaction_, since that has
                    # actually already happened due to the error above.  It brings the
                    # Python session in sync with underlying connection so that when we
                    # exec the outer with block, the context manager will not attempt to
                    # commit the session.
                    #
                    # Then, raise TryAgain to break out of these nested loops, back to
                    # the outer loop, where we'll begin a new transaction with
                    # session.begin() in the next loop iteration.
                    await session.rollback()
                    raise TryAgain()
        return runs_to_insert

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
        Given a `deployment_id` and schedule params, generates a list of flow run
        objects and associated scheduled states that represent scheduled flow runs.

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
        Given a list of flow runs to schedule, as generated by
        `_generate_scheduled_flow_runs`, inserts them into the database. Note this is a
        separate method to facilitate batch operations on many scheduled runs.

        Pass-through method for overrides.
        """
        return await models.deployments._insert_scheduled_flow_runs(
            session=session, runs=runs
        )


class RecentDeploymentsScheduler(Scheduler):
    """
    A scheduler that only schedules deployments that were updated very recently.
    This scheduler can run on a tight loop and ensure that runs from
    newly-created or updated deployments are rapidly scheduled without having to
    wait for the "main" scheduler to complete its loop.

    Note that scheduling is idempotent, so its ok for this scheduler to attempt
    to schedule the same deployments as the main scheduler. It's purpose is to
    accelerate scheduling for any deployments that users are interacting with.
    """

    # this scheduler runs on a tight loop
    loop_seconds = 5

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
                # use a slightly larger window than the loop interval to pick up
                # any deployments that were created *while* the scheduler was
                # last running (assuming the scheduler takes less than one
                # second to run). Scheduling is idempotent so picking up schedules
                # multiple times is not a concern.
                db.Deployment.updated
                >= pendulum.now().subtract(seconds=self.loop_seconds + 1),
            )
            .order_by(db.Deployment.id)
            .limit(self.deployment_batch_size)
        )
        return query


if __name__ == "__main__":
    asyncio.run(run_multiple_services([Scheduler(), RecentDeploymentsScheduler()]))
