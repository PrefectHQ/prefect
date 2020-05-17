# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import pendulum
import pytest

import prefect
from prefect_server.database import models as m
from prefect_server.services.scheduler import Scheduler


@pytest.fixture(autouse=True)
async def clear_schedules(flow_id, schedule_id):
    await m.Schedule.where(id=schedule_id).update(
        set={"last_checked": None, "last_scheduled_run_time": None}
    )
    await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()


async def test_scheduler_creates_runs():
    assert await Scheduler().schedule_flows() == 10


async def test_scheduler_creates_no_runs_if_run_twice_quickly():
    assert await Scheduler().schedule_flows() == 10
    assert await Scheduler().schedule_flows() == 0


# each dictionary should describe a schedule that does NOT run
@pytest.mark.parametrize(
    "settings",
    [
        # NOTE: these are lambdas because otherwise the timestamp is created when the
        # file is imported, not when the test is run
        lambda: {"last_checked": pendulum.now().subtract(seconds=30)},
        lambda: {"schedule_start": pendulum.now().add(days=1, minutes=1)},
        lambda: {"schedule_end": pendulum.now().subtract(minutes=1)},
        lambda: {"active": False},
    ],
)
async def test_scheduler_does_not_run(schedule_id, settings):
    await m.Schedule.where(id=schedule_id).update(set=settings())
    assert await Scheduler().schedule_flows() == 0


async def test_scheduler_does_not_run_for_archived_flows(flow_id):
    await m.Flow.where(id=flow_id).update(set={"archived": True})
    assert await Scheduler().schedule_flows() == 0


# each dictionary should describe a schedule that DOES run
@pytest.mark.parametrize(
    "settings",
    [
        # NOTE: these are lambdas because otherwise the timestamp is created when the
        # file is imported, not when the test is run
        lambda: {"last_checked": pendulum.now().subtract(minutes=1, seconds=30)},
        lambda: {"schedule_start": pendulum.now().add(days=1, minutes=-1)},
        lambda: {"schedule_end": pendulum.now().add(minutes=1)},
    ],
)
async def test_scheduler_does_run(schedule_id, settings):
    await m.Schedule.where(id=schedule_id).update(set=settings())
    assert await Scheduler().schedule_flows() == 10
