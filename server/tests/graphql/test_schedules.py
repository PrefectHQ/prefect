# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import pendulum
import pytest

import prefect
from prefect_server import api
from prefect_server.database import models
from prefect_server.utilities.exceptions import Unauthenticated, Unauthorized


@pytest.fixture(autouse=True)
async def clear_schedules(schedule_id, flow_id):
    await models.Schedule.where(id=schedule_id).update(
        set={"last_scheduled_run_time": None, "last_checked": None}
    )
    await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()


class TestSetScheduleActive:
    mutation = """
        mutation($input: set_schedule_active_input!) {
            set_schedule_active(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_schedule_active(self, run_query, schedule_id):
        await models.Schedule.where(id=schedule_id).update(set={"active": False})
        # set active
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(schedule_id=schedule_id)),
        )

        assert result.data.set_schedule_active.success is True
        schedule = await models.Schedule.where(id=schedule_id).first({"active"})
        assert schedule.active


class TestSetScheduleInactive:
    mutation = """
        mutation($input: set_schedule_inactive_input!) {
            set_schedule_inactive(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_schedule_inactive(self, run_query, schedule_id):
        # set active
        await models.Schedule.where(id=schedule_id).update(set={"active": True})

        # set inactive
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(schedule_id=schedule_id)),
        )
        assert result.data.set_schedule_inactive.success is True
        schedule = await models.Schedule.where(id=schedule_id).first({"active"})
        assert not schedule.active


class TestScheduleFlowRuns:
    mutation = """
        mutation($input: schedule_flow_runs_input!) {
            schedule_flow_runs(input: $input) {
                id
            }
        }
    """

    async def test_schedule_flow_runs(self, run_query, flow_id, schedule_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(schedule_id=schedule_id)),
        )

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

    async def test_schedule_flow_runs_with_max_runs(
        self, run_query, flow_id, schedule_id
    ):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(schedule_id=schedule_id, max_runs=20)),
        )

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 20

    async def test_call_schedule_flow_runs_twice(self, run_query, flow_id, schedule_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()

        await run_query(
            query=self.mutation,
            variables=dict(input=dict(schedule_id=schedule_id, max_runs=20)),
        )
        await run_query(
            query=self.mutation,
            variables=dict(input=dict(schedule_id=schedule_id, max_runs=20)),
        )

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 20
