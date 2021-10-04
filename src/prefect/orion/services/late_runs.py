"""
The MarkLateRuns service.
"""

import datetime
import asyncio

import sqlalchemy as sa

import prefect
from prefect.orion import models
from prefect.orion.schemas import states
from prefect.orion.services.loop_service import LoopService

from prefect.orion.utilities.database import now, date_add
from prefect.orion.models.orm import FlowRun, FlowRunState

settings = prefect.settings.orion.services


class MarkLateRuns(LoopService):
    """
    A simple loop service responsible for identifying flow runs that are "late".

    A flow run is defined as "late" if has not scheduled within a certain amount
    of time after its scheduled start time. The exact amount is configurable in
    Orion settings.
    """

    loop_seconds: float = prefect.settings.orion.services.late_runs_loop_seconds

    # mark runs late if they are this far past their expected start time
    mark_late_after: datetime.timedelta = (
        prefect.settings.orion.services.mark_late_after
    )

    batch_size: int = 100

    async def run_once(self):
        """
        Mark flow runs as late by:

        - Querying for flow runs in a scheduled state that are Scheduled to start in the past
        - For any runs past the "late" threshold, setting the flow run state to a new `Late` state
        """
        async with self.session_factory() as session:
            async with session.begin():
                last_id = None
                while True:

                    query = (
                        sa.select(
                            FlowRun.id,
                            FlowRun.next_scheduled_start_time,
                        )
                        .select_from(FlowRun)
                        .join(FlowRunState, FlowRun.state_id == FlowRunState.id)
                        .where(
                            # the next scheduled start time is in the past
                            FlowRun.next_scheduled_start_time
                            < date_add(now(), self.mark_late_after),
                            FlowRunState.type == states.StateType.SCHEDULED,
                            FlowRunState.name == "Scheduled",
                        )
                        .order_by(FlowRun.id)
                        .limit(self.batch_size)
                    )

                    # use cursor based pagination
                    if last_id:
                        query = query.where(FlowRun.id > last_id)

                    result = await session.execute(query)
                    runs = result.all()

                    # mark each run as late
                    for run in runs:
                        await models.flow_runs.set_flow_run_state(
                            session=session,
                            flow_run_id=run.id,
                            state=states.Late(
                                scheduled_time=run.next_scheduled_start_time
                            ),
                            force=True,
                        )

                    # if no runs were found, exit the loop
                    if len(runs) < self.batch_size:
                        break
                    else:
                        # record the last deployment ID
                        last_id = runs[-1].id

            self.logger.info(f"Finished monitoring for late runs.")


if __name__ == "__main__":
    asyncio.run(MarkLateRuns().start())
