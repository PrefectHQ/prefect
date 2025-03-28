"""
The Scheduler service.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any, Sequence
from uuid import UUID

import sqlalchemy as sa

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface
from prefect.server.database.dependencies import db_injector
from prefect.server.schemas.states import StateType
from prefect.server.services.base import LoopService, run_multiple_services
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE,
    PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME,
)
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now
from prefect.utilities.collections import batched_iterable


class TryAgain(Exception):
    """Internal control-flow exception used to retry the Scheduler's main loop"""


class Scheduler(LoopService):
    """
    Schedules flow runs from deployments.
    """

    # the main scheduler takes its loop interval from
    # PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS
    loop_seconds: float

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.scheduler

    def __init__(self, loop_seconds: float | None = None, **kwargs: Any):
        super().__init__(
            loop_seconds=(
                loop_seconds
                or self.loop_seconds
                or PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS.value()
            ),
            **kwargs,
        )
        self.deployment_batch_size: int = (
            PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE.value()
        )
        self.max_runs: int = PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS.value()
        self.min_runs: int = PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
        self.max_scheduled_time: datetime.timedelta = (
            PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
        )
        self.min_scheduled_time: datetime.timedelta = (
            PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME.value()
        )
        self.insert_batch_size: int = (
            PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE.value()
        )

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        Schedule flow runs by:

        - Querying for deployments with active schedules
        - Generating the next set of flow runs based on each deployments schedule
        - Inserting all scheduled flow runs into the database

        All inserted flow runs are committed to the database at the termination of the
        loop.
        """
        total_inserted_runs = 0

        last_id = None
        while True:
            async with db.session_context(begin_transaction=False) as session:
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
            for batch in batched_iterable(runs_to_insert, self.insert_batch_size):
                async with db.session_context(begin_transaction=True) as session:
                    inserted_runs = await self._insert_scheduled_flow_runs(
                        session=session, runs=list(batch)
                    )
                    total_inserted_runs += len(inserted_runs)

            # if this is the last page of deployments, exit the loop
            if len(deployment_ids) < self.deployment_batch_size:
                break
            else:
                # record the last deployment ID
                last_id = deployment_ids[-1]

        self.logger.info(f"Scheduled {total_inserted_runs} runs.")

    @db_injector
    def _get_select_deployments_to_schedule_query(
        self, db: PrefectDBInterface
    ) -> sa.Select[tuple[UUID]]:
        """
        Returns a sqlalchemy query for selecting deployments to schedule.

        The query gets the IDs of any deployments with:

            - an active schedule
            - EITHER:
                - fewer than `min_runs` auto-scheduled runs
                - OR the max scheduled time is less than `max_scheduled_time` in the future
        """
        right_now = now("UTC")
        query = (
            sa.select(db.Deployment.id)
            .select_from(db.Deployment)
            # TODO: on Postgres, this could be replaced with a lateral join that
            # sorts by `next_scheduled_start_time desc` and limits by
            # `self.min_runs` for a ~ 50% speedup. At the time of writing,
            # performance of this universal query appears to be fast enough that
            # this optimization is not worth maintaining db-specific queries
            .join(
                db.FlowRun,
                # join on matching deployments, only picking up future scheduled runs
                sa.and_(
                    db.Deployment.id == db.FlowRun.deployment_id,
                    db.FlowRun.state_type == StateType.SCHEDULED,
                    db.FlowRun.next_scheduled_start_time >= right_now,
                    db.FlowRun.auto_scheduled.is_(True),
                ),
                isouter=True,
            )
            .where(
                sa.and_(
                    db.Deployment.paused.is_not(True),
                    (
                        # Only include deployments that have at least one
                        # active schedule.
                        sa.select(db.DeploymentSchedule.deployment_id)
                        .where(
                            sa.and_(
                                db.DeploymentSchedule.deployment_id == db.Deployment.id,
                                db.DeploymentSchedule.active.is_(True),
                            )
                        )
                        .exists()
                    ),
                )
            )
            .group_by(db.Deployment.id)
            # having EITHER fewer than three runs OR runs not scheduled far enough out
            .having(
                sa.or_(
                    sa.func.count(db.FlowRun.next_scheduled_start_time) < self.min_runs,
                    sa.func.max(db.FlowRun.next_scheduled_start_time)
                    < right_now + self.min_scheduled_time,
                )
            )
            .order_by(db.Deployment.id)
            .limit(self.deployment_batch_size)
        )
        return query

    async def _collect_flow_runs(
        self,
        session: sa.orm.Session,
        deployment_ids: Sequence[UUID],
    ) -> list[dict[str, Any]]:
        runs_to_insert: list[dict[str, Any]] = []
        for deployment_id in deployment_ids:
            right_now = now("UTC")
            # guard against erroneously configured schedules
            try:
                runs_to_insert.extend(
                    await self._generate_scheduled_flow_runs(
                        session=session,
                        deployment_id=deployment_id,
                        start_time=right_now,
                        end_time=right_now + self.max_scheduled_time,
                        min_time=self.min_scheduled_time,
                        min_runs=self.min_runs,
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

    @db_injector
    async def _generate_scheduled_flow_runs(
        self,
        db: PrefectDBInterface,
        session: sa.orm.Session,
        deployment_id: UUID,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        min_time: datetime.timedelta,
        min_runs: int,
        max_runs: int,
    ) -> list[dict[str, Any]]:
        """
        Given a `deployment_id` and schedule params, generates a list of flow run
        objects and associated scheduled states that represent scheduled flow runs.

        Pass-through method for overrides.


        Args:
            session: a database session
            deployment_id: the id of the deployment to schedule
            start_time: the time from which to start scheduling runs
            end_time: runs will be scheduled until at most this time
            min_time: runs will be scheduled until at least this far in the future
            min_runs: a minimum amount of runs to schedule
            max_runs: a maximum amount of runs to schedule

        This function will generate the minimum number of runs that satisfy the min
        and max times, and the min and max counts. Specifically, the following order
        will be respected:

            - Runs will be generated starting on or after the `start_time`
            - No more than `max_runs` runs will be generated
            - No runs will be generated after `end_time` is reached
            - At least `min_runs` runs will be generated
            - Runs will be generated until at least `start_time + min_time` is reached

        """
        return await models.deployments._generate_scheduled_flow_runs(
            db,
            session=session,
            deployment_id=deployment_id,
            start_time=start_time,
            end_time=end_time,
            min_time=min_time,
            min_runs=min_runs,
            max_runs=max_runs,
        )

    async def _insert_scheduled_flow_runs(
        self,
        session: sa.orm.Session,
        runs: list[dict[str, Any]],
    ) -> Sequence[UUID]:
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
    Schedules deployments that were updated very recently

    This scheduler can run on a tight loop and ensure that runs from
    newly-created or updated deployments are rapidly scheduled without having to
    wait for the "main" scheduler to complete its loop.

    Note that scheduling is idempotent, so its ok for this scheduler to attempt
    to schedule the same deployments as the main scheduler. It's purpose is to
    accelerate scheduling for any deployments that users are interacting with.
    """

    # this scheduler runs on a tight loop
    loop_seconds: float = 5

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.scheduler

    @db_injector
    def _get_select_deployments_to_schedule_query(
        self, db: PrefectDBInterface
    ) -> sa.Select[tuple[UUID]]:
        """
        Returns a sqlalchemy query for selecting deployments to schedule
        """
        query = (
            sa.select(db.Deployment.id)
            .where(
                sa.and_(
                    db.Deployment.paused.is_not(True),
                    # use a slightly larger window than the loop interval to pick up
                    # any deployments that were created *while* the scheduler was
                    # last running (assuming the scheduler takes less than one
                    # second to run). Scheduling is idempotent so picking up schedules
                    # multiple times is not a concern.
                    db.Deployment.updated
                    >= now("UTC") - datetime.timedelta(seconds=self.loop_seconds + 1),
                    (
                        # Only include deployments that have at least one
                        # active schedule.
                        sa.select(db.DeploymentSchedule.deployment_id)
                        .where(
                            sa.and_(
                                db.DeploymentSchedule.deployment_id == db.Deployment.id,
                                db.DeploymentSchedule.active.is_(True),
                            )
                        )
                        .exists()
                    ),
                )
            )
            .order_by(db.Deployment.id)
            .limit(self.deployment_batch_size)
        )
        return query


if __name__ == "__main__":
    asyncio.run(
        run_multiple_services(
            [
                Scheduler(handle_signals=True),
                RecentDeploymentsScheduler(handle_signals=True),
            ]
        )
    )
