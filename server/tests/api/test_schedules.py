# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
import uuid

import pendulum
import pytest

import prefect
import prefect_server
from prefect_server import api
from prefect_server.database import models as m
from prefect.utilities.graphql import EnumValue


class TestSetScheduleActive:
    async def test_set_schedule_active(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(set={"active": False})
        await api.schedules.set_active(schedule_id=schedule_id)
        schedule = await m.Schedule.where(id=schedule_id).first({"active"})
        assert schedule.active

    async def test_set_schedule_active_twice(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(set={"active": False})
        await api.schedules.set_active(schedule_id=schedule_id)
        await api.schedules.set_active(schedule_id=schedule_id)
        schedule = await m.Schedule.where(id=schedule_id).first({"active"})
        assert schedule.active


class TestSetScheduleInactive:
    @pytest.fixture(autouse=True)
    async def clear_schedule(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(
            set={"last_checked": None, "last_scheduled_run_time": None}
        )

    async def test_set_schedule_inactive(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(set={"active": True})
        await api.schedules.set_inactive(schedule_id=schedule_id)
        schedule = await m.Schedule.where(id=schedule_id).first({"active"})
        assert not schedule.active

    async def test_set_schedule_inactive_twice(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(set={"active": True})
        await api.schedules.set_inactive(schedule_id=schedule_id)
        await api.schedules.set_inactive(schedule_id=schedule_id)
        schedule = await m.Schedule.where(id=schedule_id).first({"active"})
        assert not schedule.active

    async def test_set_inactive_with_bad_schedule_id(self, flow_id, schedule_id):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        with pytest.raises(ValueError) as exc:
            await api.schedules.set_inactive(schedule_id=str(uuid.uuid4()))

        assert "Schedule not found" in str(exc.value)

    async def test_set_inactive_removes_auto_scheduled_runs(self, flow_id, schedule_id):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.set_active(schedule_id=schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

        await api.schedules.set_inactive(schedule_id=schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

    async def test_set_inactive_doesnt_remove_manually_scheduled_runs(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.set_active(schedule_id=schedule_id)

        flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 11

        await api.schedules.set_inactive(schedule_id=schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 1


class TestScheduledParameters:
    async def test_schedule_creates_parametrized_flow_runs(self,):
        clock1 = prefect.schedules.clocks.IntervalClock(
            start_date=pendulum.now("UTC").add(minutes=1),
            interval=datetime.timedelta(minutes=2),
            parameter_defaults=dict(x="a"),
        )
        clock2 = prefect.schedules.clocks.IntervalClock(
            start_date=pendulum.now("UTC"),
            interval=datetime.timedelta(minutes=2),
            parameter_defaults=dict(x="b"),
        )

        flow = prefect.Flow(
            name="Test Scheduled Flow",
            schedule=prefect.schedules.Schedule(clocks=[clock1, clock2]),
        )
        flow.add_task(prefect.Parameter("x", default=1))
        flow_id = await api.flows.create_flow(serialized_flow=flow.serialize())
        schedule = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first("id")
        await m.Schedule.where(id=schedule.id).update(
            set={"last_checked": None, "last_scheduled_run_time": None}
        )
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.schedules.schedule_flow_runs(schedule.id)) == 10

        flow_runs = await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            selection_set={"parameters": True, "scheduled_start_time": True},
            order_by={"scheduled_start_time": EnumValue("asc")},
        )

        assert all([fr.parameters == dict(x="a") for fr in flow_runs[::2]])
        assert all([fr.parameters == dict(x="b") for fr in flow_runs[1::2]])


class TestScheduleRuns:
    @pytest.fixture(autouse=True)
    async def clear_schedule(self, schedule_id):
        await m.Schedule.where(id=schedule_id).update(
            set={"last_checked": None, "last_scheduled_run_time": None}
        )

    async def test_schedule_runs(self, flow_id, schedule_id):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.schedules.schedule_flow_runs(schedule_id)) == 10

    async def test_schedule_runs_doesnt_run_for_inactive_schedule(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await m.Schedule.where(id=schedule_id).update(set={"active": False})
        await api.flows.archive_flow(flow_id)
        assert await api.schedules.schedule_flow_runs(schedule_id) == []

    async def test_schedule_runs_doesnt_run_for_archived_flow(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.flows.archive_flow(flow_id)
        assert await api.schedules.schedule_flow_runs(schedule_id) == []

    async def test_schedule_runs_twice_doesnt_create_new_runs(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.schedules.schedule_flow_runs(schedule_id)) == 10
        assert await api.schedules.schedule_flow_runs(schedule_id) == []

    async def test_schedule_runs_twice_creates_new_runs_if_last_checked_and_run_time_are_cleared(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.schedule_flow_runs(schedule_id)
        await m.Schedule.where(id=schedule_id).update(
            set={"last_scheduled_run_time": None, "last_checked": None}
        )

        await api.schedules.schedule_flow_runs(schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 20

    async def test_schedule_runs_twice_does_not_create_new_runs_if_only_last_checked_is_cleared(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.schedule_flow_runs(schedule_id)
        await m.Schedule.where(id=schedule_id).update(set={"last_checked": None})
        await api.schedules.schedule_flow_runs(schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

    async def test_schedule_runs_twice_does_create_new_runs_if_only_last_checked_time_is_cleared(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.schedule_flow_runs(schedule_id)
        await m.Schedule.where(id=schedule_id).update(
            set={"last_scheduled_run_time": None}
        )
        await api.schedules.schedule_flow_runs(schedule_id)
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 20

    async def test_schedule_runs_twice_does_not_create_new_runs_if_only_last_checked_time_is_cleared_and_timeout_set(
        self, flow_id, schedule_id
    ):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.schedule_flow_runs(schedule_id)
        await m.Schedule.where(id=schedule_id).update(
            set={"last_scheduled_run_time": None}
        )
        assert not await api.schedules.schedule_flow_runs(
            schedule_id, seconds_since_last_checked=60
        )
        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

    async def test_schedule_runs_on_create_flow(self,):
        flow = prefect.Flow(
            name="test",
            schedule=prefect.schedules.IntervalSchedule(
                start_date=pendulum.datetime(2020, 1, 1),
                interval=datetime.timedelta(days=1),
            ),
        )

        run_count = await m.FlowRun.where().count()
        await api.flows.create_flow(serialized_flow=flow.serialize())
        assert await m.FlowRun.where().count() == run_count + 10

    async def test_schedule_max_runs(self, flow_id, schedule_id):
        await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.schedules.schedule_flow_runs(schedule_id, max_runs=50)

        assert await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 50
