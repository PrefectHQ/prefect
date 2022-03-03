"""
The MarkLateRuns service. Responsible for putting flow runs in a Late state if they are not started on time.
The threshold for a late run can be configured by changing `PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS`.
"""

import asyncio
import datetime

import sqlalchemy as sa

import prefect.orion.models as models
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.schemas import states
from prefect.orion.services.loop_service import LoopService
from prefect.orion.utilities.database import date_add, now
from prefect.settings import (
    PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS,
    PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS,
)


class MarkLateRuns(LoopService):
    """
    A simple loop service responsible for identifying flow runs that are "late".

    A flow run is defined as "late" if has not scheduled within a certain amount
    of time after its scheduled start time. The exact amount is configurable in
    Orion Settings.
    """

    def __init__(self, loop_seconds: float = None):
        super().__init__(
            loop_seconds or PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS.value()
        )

        # mark runs late if they are this far past their expected start time
        self.mark_late_after: datetime.timedelta = (
            PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS.value()
        )

        self.batch_size: int = 100

    @inject_db
    async def run_once(self, db: OrionDBInterface):
        """
        Mark flow runs as late by:

        - Querying for flow runs in a scheduled state that are Scheduled to start in the past
        - For any runs past the "late" threshold, setting the flow run state to a new `Late` state
        """

        session = await db.session()
        async with session:
            async with session.begin():
                last_id = None
                while True:

                    query = self._get_select_late_flow_runs_query(db=db)

                    # use cursor based pagination
                    if last_id:
                        query = query.where(db.FlowRun.id > last_id)

                    result = await session.execute(query)
                    runs = result.all()

                    # mark each run as late
                    for run in runs:
                        await self._mark_flow_run_as_late(session=session, flow_run=run)

                    # if no runs were found, exit the loop
                    if len(runs) < self.batch_size:
                        break
                    else:
                        # record the last deployment ID
                        last_id = runs[-1].id

            self.logger.info(f"Finished monitoring for late runs.")

    @inject_db
    def _get_select_late_flow_runs_query(self, db: OrionDBInterface):
        """
        Returns a sqlalchemy query for late flow runs.
        """
        query = (
            sa.select(
                db.FlowRun.id,
                db.FlowRun.next_scheduled_start_time,
            )
            .select_from(db.FlowRun)
            .join(
                db.FlowRunState,
                db.FlowRun.state_id == db.FlowRunState.id,
            )
            .where(
                # the next scheduled start time is in the past
                db.FlowRun.next_scheduled_start_time
                < date_add(now(), self.mark_late_after),
                db.FlowRunState.type == states.StateType.SCHEDULED,
                db.FlowRunState.name == "Scheduled",
            )
            .order_by(db.FlowRun.id)
            .limit(self.batch_size)
        )
        return query

    async def _mark_flow_run_as_late(
        self, session: sa.orm.Session, flow_run: OrionDBInterface.FlowRun
    ) -> None:
        """
        Mark a flow run as late.

        Pass-through method for overrides.
        """
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=states.Late(scheduled_time=flow_run.next_scheduled_start_time),
            force=True,
        )


if __name__ == "__main__":
    asyncio.run(MarkLateRuns().start())
