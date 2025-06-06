from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List

import pytest
import sqlalchemy as sa
from fastapi import status
from httpx import Response
from pydantic import TypeAdapter
from whenever import Instant

from prefect.server import models
from prefect.server.schemas import actions, core, responses, states
from prefect.server.schemas.states import StateType


def datetime_range(
    start: datetime, end: datetime, interval: timedelta
) -> Iterator[datetime]:
    """Generate a range of datetimes from start to end by interval."""
    current = start
    while current <= end:
        yield current
        current += interval


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC timezone if not already."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


dt = to_utc(datetime(2021, 7, 1))


def assert_datetime_dictionaries_equal(a, b):
    # DateTime objects will be equal if their timezones are compatible, but not
    # when embedded in a dictionary
    for dictionary_a, dictionary_b in zip(a, b):
        assert dictionary_a.keys() == dictionary_b.keys()
        for k, v in dictionary_a.items():
            assert v == dictionary_b[k]


def validate_response(response: Response, include=None) -> List[Dict[str, Any]]:
    assert response.status_code == status.HTTP_200_OK
    parsed = TypeAdapter(List[responses.HistoryResponse]).validate_python(
        response.json()
    )

    # for each interval...
    for p in parsed:
        # sort states arrays for comparison
        p.states = sorted(p.states, key=lambda s: s.state_name)

    dumped = [p.model_dump() for p in parsed]

    # grab only requested fields in the states aggregation, to make comparison simple
    if include:
        for p in dumped:
            p["states"] = [
                {k: v for k, v in s.items() if k in include} for s in p["states"]
            ]

    return dumped


@pytest.fixture(autouse=True, scope="module")
async def clear_db(db):
    """Prevent automatic database-clearing behavior after every test"""
    yield  # noqa
    async with db.session_context(begin_transaction=True) as session:
        await session.execute(db.Agent.__table__.delete())
        # work pool has a circular dependency on pool queue; delete it first
        await session.execute(db.WorkPool.__table__.delete())

        for table in reversed(db.Base.metadata.sorted_tables):
            await session.execute(table.delete())


@pytest.fixture(autouse=True, scope="module")
async def work_pool(db):
    session = await db.session()
    async with session:
        model = await models.workers.create_work_pool(
            session=session,
            work_pool=actions.WorkPoolCreate(
                name="test-work-pool-run-history",
                type="test-type",
                base_job_template={
                    "job_configuration": {"command": "{{ command }}"},
                    "variables": {
                        "properties": {
                            "command": {
                                "type": "array",
                                "title": "Command",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [],
                    },
                },
            ),
        )
        await session.commit()
    return model


@pytest.fixture(autouse=True, scope="module")
async def work_queue(db, work_pool):
    session = await db.session()
    async with session:
        model = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=actions.WorkQueueCreate(name="wq"),
        )
        await session.commit()
    return model


@pytest.fixture(autouse=True, scope="module")
async def data(db, work_queue):
    session = await db.session()
    async with session:

        def create_flow(flow):
            return models.flows.create_flow(session=session, flow=flow)

        def create_flow_run(flow_run):
            return models.flow_runs.create_flow_run(session=session, flow_run=flow_run)

        def create_task_run(task_run):
            return models.task_runs.create_task_run(session=session, task_run=task_run)

        f_1 = await create_flow(flow=core.Flow(name="f-1", tags=["db", "blue"]))
        await create_flow(flow=core.Flow(name="f-2", tags=["db"]))

        # Weekend days are Saturday (5) and Sunday (6)
        weekend_days = (5, 6)

        # have a completed flow every 12 hours except weekends
        for d in datetime_range(dt - timedelta(days=14), dt, timedelta(hours=12)):
            # skip weekends
            if d.weekday() in weekend_days:
                continue

            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["completed"],
                    state=states.Completed(timestamp=d),
                    work_queue_id=work_queue.id,
                )
            )

        # have a failed flow every 36 hours except the last 3 days
        for d in datetime_range(dt - timedelta(days=14), dt, timedelta(hours=36)):
            # skip recent runs
            if dt - timedelta(days=3) <= d < dt:
                continue

            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["failed"],
                    state=states.Failed(timestamp=d),
                )
            )

        # a few running runs in the last two days
        for d in datetime_range(dt - timedelta(days=2), dt, timedelta(hours=6)):
            await create_flow_run(
                flow_run=core.FlowRun(
                    flow_id=f_1.id,
                    tags=["running"],
                    state=states.Running(timestamp=d),
                )
            )

        # schedule new runs
        for d in datetime_range(
            dt - timedelta(days=1), dt + timedelta(days=3), timedelta(hours=6)
        ):
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
                    dynamic_key=str(r * 3),
                    state=states.Completed(timestamp=dt + timedelta(minutes=r)),
                )
            )
            await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    dynamic_key=str((r * 3) + 1),
                    state=states.Failed(timestamp=dt + timedelta(minutes=7 + r)),
                )
            )
            await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    dynamic_key=str((r * 3) + 2),
                    state=states.Running(timestamp=dt + timedelta(minutes=14 + r)),
                )
            )

        await session.commit()


@pytest.mark.parametrize("route", ["/flow_runs/history", "/task_runs/history"])
@pytest.mark.parametrize(
    "start,end,interval,expected_bins",
    [
        (dt, dt + timedelta(days=14), timedelta(days=1), 14),
        (dt, dt + timedelta(days=10), timedelta(days=1, hours=1), 10),
        (dt, dt + timedelta(days=10), timedelta(hours=6), 40),
        (dt, dt + timedelta(days=10), timedelta(hours=1), 240),
        (dt, dt + timedelta(days=1), timedelta(hours=1, minutes=6), 22),
        (dt, dt + timedelta(hours=5), timedelta(minutes=1), 300),
        (dt, dt + timedelta(days=1, hours=5), timedelta(minutes=15), 116),
    ],
)
async def test_history(
    client,
    route,
    start,
    end,
    interval,
    expected_bins,
):
    response = await client.post(
        route,
        json=dict(
            history_start=str(start),
            history_end=str(end),
            history_interval_seconds=interval.total_seconds(),
        ),
    )

    response_histories = validate_response(response)

    assert len(response_histories) == expected_bins
    assert min([r["interval_start"] for r in response_histories]) == start
    assert (
        response_histories[0]["interval_end"] - response_histories[0]["interval_start"]
        == interval
    )
    assert (
        max([r["interval_start"] for r in response_histories])
        == start + (expected_bins - 1) * interval
    )


@pytest.mark.parametrize("route", ["flow_runs", "task_runs"])
async def test_history_returns_maximum_items(client, route):
    response = await client.post(
        f"/{route}/history",
        json=dict(
            history_start=dt.isoformat(),
            history_end=(dt + timedelta(days=10)).isoformat(),
            history_interval_seconds=timedelta(minutes=1).total_seconds(),
        ),
    )

    assert response.status_code == status.HTTP_200_OK

    # only first 500 items returned
    assert len(response.json()) == 500

    intervals = [
        Instant.parse_common_iso(r["interval_start"]).py_datetime()
        for r in response.json()
    ]
    assert min(intervals) == dt
    assert max(intervals) == dt + timedelta(minutes=499)


async def test_daily_bins_flow_runs(client):
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=5)),
            history_end=str(dt + timedelta(days=1)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=dt - timedelta(days=5),
                interval_end=dt - timedelta(days=4),
                states=[
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=1,
                    )
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=4),
                interval_end=dt - timedelta(days=3),
                states=[
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=1,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=3),
                interval_end=dt - timedelta(days=2),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    )
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=2),
                interval_end=dt - timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=1),
                interval_end=dt,
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=4,
                    ),
                    dict(
                        state_name="Scheduled",
                        state_type=StateType.SCHEDULED,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt,
                interval_end=dt + timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=1,
                    ),
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=2,
                    ),
                    dict(
                        state_name="Scheduled",
                        state_type=StateType.SCHEDULED,
                        count_runs=4,
                    ),
                ],
            ),
        ],
    )


async def test_weekly_bins_flow_runs(client):
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=16)),
            history_end=str(dt + timedelta(days=6)),
            history_interval_seconds=timedelta(days=7).total_seconds(),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=dt - timedelta(days=16),
                interval_end=dt - timedelta(days=9),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=6,
                    ),
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=9),
                interval_end=dt - timedelta(days=2),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=10,
                    ),
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=2),
                interval_end=dt + timedelta(days=5),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=5,
                    ),
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=10,
                    ),
                    dict(
                        state_name="Scheduled",
                        state_type=StateType.SCHEDULED,
                        count_runs=17,
                    ),
                ],
            ),
            dict(
                interval_start=dt + timedelta(days=5),
                interval_end=dt + timedelta(days=12),
                states=[],
            ),
        ],
    )


async def test_weekly_bins_with_filters_flow_runs(client):
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=16)),
            history_end=str(dt + timedelta(days=6)),
            history_interval_seconds=timedelta(days=7).total_seconds(),
            flow_runs=dict(state=dict(type=dict(any_=["FAILED", "SCHEDULED"]))),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=dt - timedelta(days=16),
                interval_end=dt - timedelta(days=9),
                states=[
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=9),
                interval_end=dt - timedelta(days=2),
                states=[
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=4,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=2),
                interval_end=dt + timedelta(days=5),
                states=[
                    dict(
                        state_name="Scheduled",
                        state_type=StateType.SCHEDULED,
                        count_runs=17,
                    ),
                ],
            ),
            dict(
                interval_start=dt + timedelta(days=5),
                interval_end=dt + timedelta(days=12),
                states=[],
            ),
        ],
    )


async def test_weekly_bins_with_filters_work_pools(client, work_pool):
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=5)),
            history_end=str(dt + timedelta(days=1)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
            work_pools=dict(name=dict(any_=[work_pool.name])),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    # Only completed runs are associated with the work pool
    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=dt - timedelta(days=5),
                interval_end=dt - timedelta(days=4),
                states=[],
            ),
            dict(
                interval_start=dt - timedelta(days=4),
                interval_end=dt - timedelta(days=3),
                states=[],
            ),
            dict(
                interval_start=dt - timedelta(days=3),
                interval_end=dt - timedelta(days=2),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    )
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=2),
                interval_end=dt - timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=1),
                interval_end=dt,
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                ],
            ),
            dict(
                interval_start=dt,
                interval_end=dt + timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=1,
                    ),
                ],
            ),
        ],
    )


async def test_weekly_bins_with_filters_work_queues(client, work_queue):
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=5)),
            history_end=str(dt + timedelta(days=1)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
            work_queues=dict(id=dict(any_=[str(work_queue.id)])),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    # Only completed runs are associated with the work queue
    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=dt - timedelta(days=5),
                interval_end=dt - timedelta(days=4),
                states=[],
            ),
            dict(
                interval_start=dt - timedelta(days=4),
                interval_end=dt - timedelta(days=3),
                states=[],
            ),
            dict(
                interval_start=dt - timedelta(days=3),
                interval_end=dt - timedelta(days=2),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    )
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=2),
                interval_end=dt - timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                ],
            ),
            dict(
                interval_start=dt - timedelta(days=1),
                interval_end=dt,
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=2,
                    ),
                ],
            ),
            dict(
                interval_start=dt,
                interval_end=dt + timedelta(days=1),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=1,
                    ),
                ],
            ),
        ],
    )


async def test_5_minute_bins_task_runs(client):
    response = await client.post(
        "/task_runs/history",
        json=dict(
            history_start=str(dt - timedelta(minutes=5)),
            history_end=str(dt + timedelta(minutes=15)),
            history_interval_seconds=timedelta(minutes=5).total_seconds(),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=to_utc(datetime(2021, 6, 30, 23, 55)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 0)),
                states=[],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 0)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 5)),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=5,
                    )
                ],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 5)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 10)),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=5,
                    ),
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=3,
                    ),
                ],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 10)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 15)),
                states=[
                    dict(
                        state_name="Failed",
                        state_type=StateType.FAILED,
                        count_runs=5,
                    ),
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=1,
                    ),
                ],
            ),
        ],
    )


async def test_5_minute_bins_task_runs_with_filter(client):
    response = await client.post(
        "/task_runs/history",
        json=dict(
            history_start=str(dt - timedelta(minutes=5)),
            history_end=str(dt + timedelta(minutes=15)),
            history_interval_seconds=timedelta(minutes=5).total_seconds(),
            task_runs=dict(state=dict(type=dict(any_=["COMPLETED", "RUNNING"]))),
        ),
    )

    response_histories = validate_response(
        response, include={"state_type", "state_name", "count_runs"}
    )

    assert_datetime_dictionaries_equal(
        response_histories,
        [
            dict(
                interval_start=to_utc(datetime(2021, 6, 30, 23, 55)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 0)),
                states=[],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 0)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 5)),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=5,
                    )
                ],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 5)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 10)),
                states=[
                    dict(
                        state_name="Completed",
                        state_type=StateType.COMPLETED,
                        count_runs=5,
                    ),
                ],
            ),
            dict(
                interval_start=to_utc(datetime(2021, 7, 1, 0, 10)),
                interval_end=to_utc(datetime(2021, 7, 1, 0, 15)),
                states=[
                    dict(
                        state_name="Running",
                        state_type=StateType.RUNNING,
                        count_runs=1,
                    ),
                ],
            ),
        ],
    )


@pytest.mark.parametrize("route", ["flow_runs", "task_runs"])
async def test_last_bin_contains_end_date(client, route):
    """The last bin contains the end date, so its own end could be after the history end"""
    response = await client.post(
        f"/{route}/history",
        json=dict(
            history_start=str(dt),
            history_end=str(dt + timedelta(days=1, minutes=30)),
            history_interval_seconds=timedelta(days=1).total_seconds(),
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    parsed = TypeAdapter(List[responses.HistoryResponse]).validate_python(
        response.json()
    )
    assert len(parsed) == 2
    assert parsed[0].interval_start == dt
    assert parsed[0].interval_end == dt + timedelta(days=1)
    assert parsed[1].interval_start == dt + timedelta(days=1)
    assert parsed[1].interval_end == dt + timedelta(days=2)


async def test_flow_run_lateness(client, session):
    await session.execute(sa.text("delete from flow where true;"))

    f = await models.flows.create_flow(session=session, flow=core.Flow(name="lateness"))

    # started 3 seconds late
    fr = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=core.FlowRun(
            flow_id=f.id, state=states.Pending(timestamp=dt - timedelta(minutes=40))
        ),
    )
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=fr.id,
        state=states.Running(timestamp=dt - timedelta(minutes=39, seconds=57)),
    )
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=fr.id,
        state=states.Completed(timestamp=dt),
        force=True,
    )

    # started 10 minutes late, still running
    fr2 = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=core.FlowRun(
            flow_id=f.id,
            state=states.Scheduled(
                scheduled_time=dt - timedelta(minutes=15),
            ),
        ),
    )
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=fr2.id,
        state=states.Pending(timestamp=dt - timedelta(minutes=6)),
        force=True,
    )
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=fr2.id,
        state=states.Running(timestamp=dt - timedelta(minutes=5)),
        force=True,
    )

    # never started
    await models.flow_runs.create_flow_run(
        session=session,
        flow_run=core.FlowRun(
            flow_id=f.id,
            state=states.Scheduled(scheduled_time=dt - timedelta(minutes=1)),
        ),
    )
    await models.flow_runs.create_flow_run(
        session=session,
        flow_run=core.FlowRun(
            flow_id=f.id,
            state=states.Scheduled(scheduled_time=dt - timedelta(seconds=25)),
        ),
    )

    await session.commit()

    request_time = datetime.now(timezone.utc)
    response = await client.post(
        "/flow_runs/history",
        json=dict(
            history_start=str(dt - timedelta(days=1)),
            history_end=str(dt + timedelta(days=1)),
            history_interval_seconds=timedelta(days=2).total_seconds(),
            flows=dict(id=dict(any_=[str(f.id)])),
        ),
    )
    response_histories = validate_response(response)
    interval = response_histories[0]

    assert interval["interval_start"] == dt - timedelta(days=1)
    assert interval["interval_end"] == dt + timedelta(days=1)

    # -------------------------------- COMPLETED

    assert interval["states"][0]["state_type"] == StateType.COMPLETED
    assert interval["states"][0]["count_runs"] == 1
    assert interval["states"][0]["sum_estimated_run_time"] == timedelta(
        minutes=39, seconds=57
    )
    assert interval["states"][0]["sum_estimated_lateness"] == timedelta(seconds=3)

    # -------------------------------- RUNNING

    assert interval["states"][1]["state_type"] == StateType.RUNNING
    assert interval["states"][1]["count_runs"] == 1

    expected_run_time = datetime.now(timezone.utc) - (dt - timedelta(minutes=5))
    assert (
        expected_run_time - timedelta(seconds=2)
        < interval["states"][1]["sum_estimated_run_time"]
        < expected_run_time
    )
    assert interval["states"][1]["sum_estimated_lateness"] == timedelta(seconds=600)

    # -------------------------------- SCHEDULED

    assert interval["states"][2]["state_type"] == StateType.SCHEDULED
    assert interval["states"][2]["count_runs"] == 2
    assert interval["states"][2]["sum_estimated_run_time"] == timedelta(0)

    expected_lateness = (request_time - (dt - timedelta(minutes=1))) + (
        request_time - (dt - timedelta(seconds=25))
    )

    # SQLite does not store microseconds. Hence each of the two
    # Scheduled runs estimated lateness can be 'off' by up to
    # a second based on how we estimate the 'current' time used by the api.
    assert (
        abs(
            (
                expected_lateness
                - timedelta(seconds=2)
                - interval["states"][2]["sum_estimated_lateness"]
            ).total_seconds()
        )
        < 2.5
    )
