from typing import List
from datetime import timedelta

import pendulum
import pydantic
import pytest

from prefect.orion import models
from prefect.orion.api.ui import TimelineResponse
from prefect.orion.schemas import core, states
from prefect.orion.utilities.database import get_session_factory

dt = pendulum.datetime(2021, 10, 1)


@pytest.fixture(autouse=True, scope="module")
async def clear_db():
    """Prevent automatic database-clearing behavior after every test"""
    pass


@pytest.fixture(autouse=True, scope="module")
async def data(database_engine):

    session_factory = await get_session_factory(bind=database_engine)
    async with session_factory() as session:

        create_flow = lambda flow: models.flows.create_flow(session=session, flow=flow)
        create_flow_run = lambda flow_run: models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        create_task_run = lambda task_run: models.task_runs.create_task_run(
            session=session, task_run=task_run
        )

        f_1 = await create_flow(flow=core.Flow(name="f-1", tags=["db", "blue"]))
        f_2 = await create_flow(flow=core.Flow(name="f-2", tags=["db"]))

        # have a completed flow every 12 hours except weekends
        for d in pendulum.period(dt.subtract(days=14), dt).range("hours", 12):

            # skip weekends
            if d.day_of_week in (0, 6):
                continue

            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["completed"],
                    state=states.Completed(timestamp=d),
                )
            )

        # have a failed flow every 36 hours except the last 3 days
        for d in pendulum.period(dt.subtract(days=14), dt).range("hours", 36):

            # skip recent runs
            if dt.subtract(days=3) <= d < dt:
                continue

            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["failed"],
                    state=states.Failed(timestamp=d),
                )
            )

        # a few running runs in the last two days
        for d in pendulum.period(dt.subtract(days=2), dt).range("hours", 6):
            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["running"],
                    state=states.Running(timestamp=d),
                )
            )

        # schedule new runs
        for d in pendulum.period(dt.subtract(days=1), dt.add(days=3)).range("hours", 6):
            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["scheduled"],
                    state=states.Scheduled(scheduled_time=d),
                )
            )

        await session.commit()


@pytest.mark.parametrize(
    "start,end,interval,expected_bins",
    [
        (dt, dt.add(days=14), timedelta(days=1), 14),
        (dt, dt.add(days=10), timedelta(days=1, hours=1), 10),
        (dt, dt.add(days=10), timedelta(hours=6), 40),
        (dt, dt.add(days=10), timedelta(hours=1), 240),
        (dt, dt.add(days=1), timedelta(hours=1, minutes=6), 22),
        (dt, dt.add(hours=5), timedelta(minutes=1), 300),
        (dt, dt.add(days=1, hours=5), timedelta(minutes=15), 116),
    ],
)
async def test_timeline(client, start, end, interval, expected_bins):
    response = await client.get(
        "/flow_runs/timeline",
        json=dict(
            timeline_start=str(start),
            timeline_end=str(end),
            timeline_interval_seconds=interval.total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[TimelineResponse], response.json())
    assert len(parsed) == expected_bins
    assert min([r.interval_start for r in parsed]) == start
    assert parsed[0].interval_end - parsed[0].interval_start == interval
    assert (
        max([r.interval_start for r in parsed])
        == start + (expected_bins - 1) * interval
    )


async def test_timeline_returns_maximum_items(client):
    response = await client.get(
        "/flow_runs/timeline",
        json=dict(
            timeline_start=str(dt),
            timeline_end=str(dt.add(days=10)),
            timeline_interval_seconds=timedelta(minutes=1).total_seconds(),
        ),
    )

    assert response.status_code == 200

    # only first 500 items returned
    assert len(response.json()) == 500
    assert min([r["interval_start"] for r in response.json()]) == str(dt)
    assert max([r["interval_start"] for r in response.json()]) == str(
        dt.add(minutes=499)
    )


async def test_daily_bins(client):
    response = await client.get(
        "/flow_runs/timeline",
        json=dict(
            timeline_start=str(dt.subtract(days=16)),
            timeline_end=str(dt.add(days=6)),
            timeline_interval_seconds=timedelta(days=1).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[TimelineResponse], response.json())
    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 15),
            interval_end=pendulum.datetime(2021, 9, 16),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 16),
            interval_end=pendulum.datetime(2021, 9, 17),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 17),
            interval_end=pendulum.datetime(2021, 9, 18),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 18),
            interval_end=pendulum.datetime(2021, 9, 19),
            states={states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 19),
            interval_end=pendulum.datetime(2021, 9, 20),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 20),
            interval_end=pendulum.datetime(2021, 9, 21),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 21),
            interval_end=pendulum.datetime(2021, 9, 22),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 22),
            interval_end=pendulum.datetime(2021, 9, 23),
            states={states.StateType.COMPLETED: 2},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 23),
            interval_end=pendulum.datetime(2021, 9, 24),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 24),
            interval_end=pendulum.datetime(2021, 9, 25),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 25),
            interval_end=pendulum.datetime(2021, 9, 26),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 26),
            interval_end=pendulum.datetime(2021, 9, 27),
            states={states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 27),
            interval_end=pendulum.datetime(2021, 9, 28),
            states={states.StateType.COMPLETED: 2, states.StateType.FAILED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 28),
            interval_end=pendulum.datetime(2021, 9, 29),
            states={states.StateType.COMPLETED: 2},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 9, 30),
            states={states.StateType.COMPLETED: 2, states.StateType.RUNNING: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 30),
            interval_end=pendulum.datetime(2021, 10, 1),
            states={
                states.StateType.COMPLETED: 2,
                states.StateType.RUNNING: 4,
                states.StateType.SCHEDULED: 4,
            },
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1),
            interval_end=pendulum.datetime(2021, 10, 2),
            states={
                states.StateType.COMPLETED: 1,
                states.StateType.RUNNING: 1,
                states.StateType.SCHEDULED: 4,
            },
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 2),
            interval_end=pendulum.datetime(2021, 10, 3),
            states={states.StateType.SCHEDULED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 3),
            interval_end=pendulum.datetime(2021, 10, 4),
            states={states.StateType.SCHEDULED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 4),
            interval_end=pendulum.datetime(2021, 10, 5),
            states={states.StateType.SCHEDULED: 1},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 5),
            interval_end=pendulum.datetime(2021, 10, 6),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 6),
            interval_end=pendulum.datetime(2021, 10, 7),
            states={},
        ),
    ]


async def test_weekly_bins(client):
    response = await client.get(
        "/flow_runs/timeline",
        json=dict(
            timeline_start=str(dt.subtract(days=16)),
            timeline_end=str(dt.add(days=6)),
            timeline_interval_seconds=timedelta(days=7).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[TimelineResponse], response.json())
    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 15),
            interval_end=pendulum.datetime(2021, 9, 22),
            states={states.StateType.COMPLETED: 6, states.StateType.FAILED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 22),
            interval_end=pendulum.datetime(2021, 9, 29),
            states={states.StateType.COMPLETED: 10, states.StateType.FAILED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 10, 6),
            states={
                states.StateType.COMPLETED: 5,
                states.StateType.RUNNING: 9,
                states.StateType.SCHEDULED: 17,
            },
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 6),
            interval_end=pendulum.datetime(2021, 10, 13),
            states={},
        ),
    ]


async def test_weekly_bins_with_filters(client):
    response = await client.get(
        "/flow_runs/timeline",
        json=dict(
            timeline_start=str(dt.subtract(days=16)),
            timeline_end=str(dt.add(days=6)),
            timeline_interval_seconds=timedelta(days=7).total_seconds(),
            flow_runs=dict(states=["FAILED"]),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[TimelineResponse], response.json())
    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 15),
            interval_end=pendulum.datetime(2021, 9, 22),
            states={states.StateType.FAILED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 22),
            interval_end=pendulum.datetime(2021, 9, 29),
            states={states.StateType.FAILED: 4},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 10, 6),
            states={},
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 6),
            interval_end=pendulum.datetime(2021, 10, 13),
            states={},
        ),
    ]
