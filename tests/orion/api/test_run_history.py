from typing import List
from datetime import timedelta

import pendulum
import pydantic
import pytest

from prefect.orion import models
from prefect.orion.schemas import core, states, responses
from prefect.orion.utilities.database import get_session_factory
from prefect.orion.schemas.states import StateType

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

        # -------------- task runs
        fr = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["running"],
                state=states.Running(timestamp=dt),
            )
        )

        for r in range(10):
            await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    state=states.Completed(timestamp=dt.add(minutes=r)),
                )
            )
            await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    state=states.Failed(timestamp=dt.add(minutes=7 + r)),
                )
            )
            await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    state=states.Running(timestamp=dt.add(minutes=14 + r)),
                )
            )

        await session.commit()


@pytest.mark.parametrize("request_method", ["post", "get"])
@pytest.mark.parametrize("route", ["/flow_runs/history/", "/task_runs/history/"])
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
async def test_history(
    request_method,
    client,
    route,
    start,
    end,
    interval,
    expected_bins,
):
    response = await getattr(client, request_method)(
        route,
        json=dict(
            history_start=str(start),
            history_end=str(end),
            history_interval_seconds=interval.total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    assert len(parsed) == expected_bins
    assert min([r.interval_start for r in parsed]) == start
    assert parsed[0].interval_end - parsed[0].interval_start == interval
    assert (
        max([r.interval_start for r in parsed])
        == start + (expected_bins - 1) * interval
    )


@pytest.mark.parametrize("request_method", ["post", "get"])
@pytest.mark.parametrize("route", ["flow_runs", "task_runs"])
async def test_history_returns_maximum_items(request_method, client, route):
    response = await getattr(client, request_method)(
        f"/{route}/history",
        json=dict(
            history_start=str(dt),
            history_end=str(dt.add(days=10)),
            history_interval_seconds=timedelta(minutes=1).total_seconds(),
        ),
    )

    assert response.status_code == 200

    # only first 500 items returned
    assert len(response.json()) == 500
    assert min([r["interval_start"] for r in response.json()]) == str(dt)
    assert max([r["interval_start"] for r in response.json()]) == str(
        dt.add(minutes=499)
    )


@pytest.mark.parametrize("request_method", ["post", "get"])
async def test_daily_bins_flow_runs(request_method, client):
    response = await getattr(client, request_method)(
        "/flow_runs/history/",
        json=dict(
            history_start=str(dt.subtract(days=5)),
            history_end=str(dt.add(days=1)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())

    # sort states arrays for comparison
    for p in parsed:
        p.states = sorted(p.states, key=lambda s: s.name)

    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 26),
            interval_end=pendulum.datetime(2021, 9, 27),
            states=[dict(name="Failed", type=StateType.FAILED, count=1)],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 27),
            interval_end=pendulum.datetime(2021, 9, 28),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=2),
                dict(name="Failed", type=StateType.FAILED, count=1),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 28),
            interval_end=pendulum.datetime(2021, 9, 29),
            states=[dict(name="Completed", type=StateType.COMPLETED, count=2)],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 9, 30),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=2),
                dict(name="Running", type=StateType.RUNNING, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 30),
            interval_end=pendulum.datetime(2021, 10, 1),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=2),
                dict(name="Running", type=StateType.RUNNING, count=4),
                dict(name="Scheduled", type=StateType.SCHEDULED, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1),
            interval_end=pendulum.datetime(2021, 10, 2),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=1),
                dict(name="Running", type=StateType.RUNNING, count=2),
                dict(name="Scheduled", type=StateType.SCHEDULED, count=4),
            ],
        ),
    ]


@pytest.mark.parametrize("request_method", ["post", "get"])
async def test_weekly_bins_flow_runs(request_method, client):
    response = await getattr(client, request_method)(
        "/flow_runs/history/",
        json=dict(
            history_start=str(dt.subtract(days=16)),
            history_end=str(dt.add(days=6)),
            history_interval_seconds=timedelta(days=7).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    # sort states arrays for comparison
    for p in parsed:
        p.states = sorted(p.states, key=lambda s: s.name)

    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 15),
            interval_end=pendulum.datetime(2021, 9, 22),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=6),
                dict(name="Failed", type=StateType.FAILED, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 22),
            interval_end=pendulum.datetime(2021, 9, 29),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=10),
                dict(name="Failed", type=StateType.FAILED, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 10, 6),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=5),
                dict(name="Running", type=StateType.RUNNING, count=10),
                dict(name="Scheduled", type=StateType.SCHEDULED, count=17),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 6),
            interval_end=pendulum.datetime(2021, 10, 13),
            states=[],
        ),
    ]


@pytest.mark.parametrize("request_method", ["post", "get"])
async def test_weekly_bins_with_filters_flow_runs(request_method, client):
    response = await getattr(client, request_method)(
        "/flow_runs/history/",
        json=dict(
            history_start=str(dt.subtract(days=16)),
            history_end=str(dt.add(days=6)),
            history_interval_seconds=timedelta(days=7).total_seconds(),
            flow_runs=dict(states=["FAILED", "SCHEDULED"]),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    # sort states arrays for comparison
    for p in parsed:
        p.states = sorted(p.states, key=lambda s: s.name)

    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 15),
            interval_end=pendulum.datetime(2021, 9, 22),
            states=[
                dict(name="Failed", type=StateType.FAILED, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 22),
            interval_end=pendulum.datetime(2021, 9, 29),
            states=[
                dict(name="Failed", type=StateType.FAILED, count=4),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 9, 29),
            interval_end=pendulum.datetime(2021, 10, 6),
            states=[
                dict(name="Scheduled", type=StateType.SCHEDULED, count=17),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 6),
            interval_end=pendulum.datetime(2021, 10, 13),
            states=[],
        ),
    ]


@pytest.mark.parametrize("request_method", ["post", "get"])
async def test_5_minute_bins_task_runs(request_method, client):
    response = await getattr(client, request_method)(
        "/task_runs/history/",
        json=dict(
            history_start=str(dt.subtract(minutes=5)),
            history_end=str(dt.add(minutes=15)),
            history_interval_seconds=timedelta(minutes=5).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    # sort states arrays for comparison
    for p in parsed:
        p.states = sorted(p.states, key=lambda s: s.name)

    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 30, 23, 55),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 0),
            states=[],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 0),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 5),
            states=[dict(name="Completed", type=StateType.COMPLETED, count=5)],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 5),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 10),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=5),
                dict(name="Failed", type=StateType.FAILED, count=3),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 10),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 15),
            states=[
                dict(name="Failed", type=StateType.FAILED, count=5),
                dict(name="Running", type=StateType.RUNNING, count=1),
            ],
        ),
    ]


@pytest.mark.parametrize("request_method", ["post", "get"])
async def test_5_minute_bins_task_runs_with_filter(request_method, client):
    response = await getattr(client, request_method)(
        "/task_runs/history/",
        json=dict(
            history_start=str(dt.subtract(minutes=5)),
            history_end=str(dt.add(minutes=15)),
            history_interval_seconds=timedelta(minutes=5).total_seconds(),
            task_runs=dict(states=["COMPLETED", "RUNNING"]),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    # sort states arrays for comparison
    for p in parsed:
        p.states = sorted(p.states, key=lambda s: s.name)

    assert parsed == [
        dict(
            interval_start=pendulum.datetime(2021, 9, 30, 23, 55),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 0),
            states=[],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 0),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 5),
            states=[dict(name="Completed", type=StateType.COMPLETED, count=5)],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 5),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 10),
            states=[
                dict(name="Completed", type=StateType.COMPLETED, count=5),
            ],
        ),
        dict(
            interval_start=pendulum.datetime(2021, 10, 1, 0, 10),
            interval_end=pendulum.datetime(2021, 10, 1, 0, 15),
            states=[
                dict(name="Running", type=StateType.RUNNING, count=1),
            ],
        ),
    ]


@pytest.mark.parametrize("request_method", ["post", "get"])
@pytest.mark.parametrize("route", ["flow_runs", "task_runs"])
async def test_last_bin_contains_end_date(request_method, client, route):
    """The last bin contains the end date, so its own end could be after the history end"""
    response = await getattr(client, request_method)(
        f"/{route}/history",
        json=dict(
            history_start=str(dt),
            history_end=str(dt.add(days=1, minutes=30)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
        ),
    )

    assert response.status_code == 200
    parsed = pydantic.parse_obj_as(List[responses.HistoryResponse], response.json())
    assert len(parsed) == 2
    assert parsed[0].interval_start == dt
    assert parsed[0].interval_end == dt.add(days=1)
    assert parsed[1].interval_start == dt.add(days=1)
    assert parsed[1].interval_end == dt.add(days=2)
