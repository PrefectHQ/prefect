# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio

import pendulum

import prefect
import prefect_server
from prefect.engine.state import Scheduled
from prefect.utilities.graphql import EnumValue
from prefect_server import api
from prefect_server.database import models
from prefect_server.services.loop_service import LoopService


class Scheduler(LoopService):
    """
    The Scheduler is a service that creates new flow runs for flows with active schedules.

    Schedules that are eligible for scheduling have the following properties:
        - the schedule has already started, or starts within the next 24 hours
        - the schedule has not ended
        - the schedule is active
        - the schedule's flow is not archived

    The Scheduler loads 100 flows matching this description, ordered by maximum time
    since the last time they were checked. It attempts to schedule new runs for all 100,
    using a time-based lock of 60 seconds to allow safe concurrent access (in the case of
    multiple scheduler services).
    """

    loop_seconds_config_key = "services.scheduler.scheduler_loop_seconds"
    loop_seconds_default = 300

    async def schedule_flows(self, n_flows=100) -> int:
        """

        Args:
            - n_flows (int): the maximum number of flows to schedule

        Returns:
            - int: The number of scheduled runs
        """

        now = pendulum.now("utc")

        # load 100 rows from the schedules table
        schedules = await models.Schedule.where(
            {
                # schedule is active
                "active": {"_eq": True},
                # ensure the flow is not archived
                "flow": {"archived": {"_eq": False}},
                # schedule has already started, or will start within the next day
                "_and": [
                    {
                        "_or": [
                            {"schedule_start": {"_lte": str(now.add(days=1))}},
                            {"schedule_start": {"_is_null": True}},
                        ]
                    },
                    # schedule has not yet ended
                    {
                        "_or": [
                            {"schedule_end": {"_gte": str(now)}},
                            {"schedule_end": {"_is_null": True}},
                        ]
                    },
                ],
            }
        ).get(
            selection_set={"id", "flow_id", "last_checked"},
            order_by=[{"last_checked": EnumValue("asc_nulls_first")}],
            limit=n_flows,
        )

        runs_scheduled = 0

        # concurrently schedule all runs
        all_run_ids = await asyncio.gather(
            *[
                api.schedules.schedule_flow_runs(
                    schedule.id, seconds_since_last_checked=60
                )
                for schedule in schedules
            ]
        )

        new_runs = sum(len(ids) for ids in all_run_ids)
        self.logger.info(f"Scheduled {new_runs} flow runs.")
        runs_scheduled += new_runs

        return runs_scheduled

    async def run_once(self) -> None:
        """
        Run the scheduler loop one time.

        As long as `schedule_flows` indicates that at least one run was scheduled, the
        loop resumes quickly. If `schedule_flows` schedules no flows, we finish this iteration.
        """
        runs_scheduled = True

        while runs_scheduled:
            runs_scheduled = await self.schedule_flows()
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(Scheduler().run())
