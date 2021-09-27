import datetime
import asyncio

import pendulum
import sqlalchemy as sa

import prefect
from prefect.orion import models
from prefect.orion.schemas import states
from prefect.orion.services.loop_service import LoopService

from prefect.orion.utilities.database import now, date_add
from prefect.orion.models.orm import FlowRun, FlowRunState

settings = prefect.settings.orion.services


class MarkLateRuns(LoopService):

    loop_seconds: float = prefect.settings.orion.services.late_runs_loop_seconds

    # mark runs late if they are this far past their expected start time
    mark_late_after: datetime.timedelta = (
        prefect.settings.orion.services.mark_late_after
    )

    batch_size: int = 100

    async def run_once(self):
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
