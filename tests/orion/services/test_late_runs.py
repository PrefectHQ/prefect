import pytest
import datetime
import pendulum
from prefect.orion import models, schemas
from prefect.orion.services.late_runs import MarkLateRuns


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


async def test_mark_late_runs(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert late_run.next_scheduled_start_time == st

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2


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
