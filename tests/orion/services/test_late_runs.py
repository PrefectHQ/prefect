import datetime

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.services.late_runs import MarkLateRuns
from prefect.settings import (
    PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS,
    temporary_settings,
)


@pytest.fixture
async def late_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now().subtract(minutes=1)
                ),
            ),
        )


@pytest.fixture
async def future_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now().add(minutes=1)
                ),
            ),
        )


@pytest.fixture
async def now_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Scheduled(scheduled_time=pendulum.now()),
            ),
        )


async def test_marks_late_run(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert (
        late_run.next_scheduled_start_time == st
    ), "Next scheduled time is set by orchestration rules correctly"

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_marks_late_run_at_buffer(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert (
        late_run.next_scheduled_start_time == st
    ), "Next scheduled time is set by orchestration rules correctly"

    with temporary_settings(
        updates={PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS: 60}
    ):
        await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_does_not_mark_run_late_if_within_buffer(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert (
        late_run.next_scheduled_start_time == st
    ), "Next scheduled time is set by orchestration rules correctly"

    with temporary_settings(
        updates={PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS: 61}
    ):
        await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Scheduled"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_does_not_mark_run_late_if_in_future(session, future_run):
    assert future_run.state.name == "Scheduled"
    st = future_run.state.state_details.scheduled_time
    assert (
        future_run.next_scheduled_start_time == st
    ), "Next scheduled time is set by orchestration rules correctly"

    await MarkLateRuns().start(loops=1)

    await session.refresh(future_run)
    assert future_run.state.name == "Scheduled"
    st2 = future_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_does_not_mark_run_late_if_now(session, now_run):
    # The 'now' time check during the run will be after the 'now' scheduled time on the
    # run, but it should still be within the 'mark late after' buffer.
    assert now_run.state.name == "Scheduled"
    st = now_run.state.state_details.scheduled_time
    assert (
        now_run.next_scheduled_start_time == st
    ), "Next scheduled time is set by orchestration rules correctly"

    await MarkLateRuns().start(loops=1)

    await session.refresh(now_run)
    assert now_run.state.name == "Scheduled"
    st2 = now_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_mark_late_runs_doesnt_visit_runs_twice(session, late_run):
    assert late_run.state.name == "Scheduled"
    si = late_run.state.id
    st = late_run.state.timestamp

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    si2 = late_run.state.id
    st2 = late_run.state.timestamp
    assert si != si2
    assert st != st2

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    si3 = late_run.state.id
    st3 = late_run.state.timestamp
    # same timestamp; unchanged state
    assert si2 == si3
    assert st2 == st3
