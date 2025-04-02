from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest import mock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.services.late_runs import MarkLateRuns
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS,
    temporary_settings,
)

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMFlowRun


@pytest.fixture
async def late_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Scheduled(
                    scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=1)
                ),
            ),
        )


@pytest.fixture
async def late_run_2(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Scheduled(
                    scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=1)
                ),
            ),
        )


@pytest.fixture
async def pending_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Pending(),
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
                    scheduled_time=datetime.now(timezone.utc) + timedelta(minutes=1)
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
                state=schemas.states.Scheduled(
                    scheduled_time=datetime.now(timezone.utc)
                ),
            ),
        )


async def test_marks_late_run(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert late_run.next_scheduled_start_time == st, (
        "Next scheduled time is set by orchestration rules correctly"
    )

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_marks_late_run_at_buffer(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert late_run.next_scheduled_start_time == st, (
        "Next scheduled time is set by orchestration rules correctly"
    )

    with temporary_settings(updates={PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS: 60}):
        await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_does_not_mark_run_late_if_within_buffer(session, late_run):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert late_run.next_scheduled_start_time == st, (
        "Next scheduled time is set by orchestration rules correctly"
    )

    with temporary_settings(updates={PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS: 61}):
        await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    assert late_run.state.name == "Scheduled"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2, "Scheduled time is unchanged"


async def test_does_not_mark_run_late_if_in_future(session, future_run):
    assert future_run.state.name == "Scheduled"
    st = future_run.state.state_details.scheduled_time
    assert future_run.next_scheduled_start_time == st, (
        "Next scheduled time is set by orchestration rules correctly"
    )

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
    assert now_run.next_scheduled_start_time == st, (
        "Next scheduled time is set by orchestration rules correctly"
    )

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


async def test_mark_late_runs_marks_multiple_runs_as_late(
    session, late_run, late_run_2
):
    assert late_run.state.name == "Scheduled"
    assert late_run_2.state.name == "Scheduled"

    await MarkLateRuns().start(loops=1)

    await session.refresh(late_run)
    await session.refresh(late_run_2)

    assert late_run.state_name == "Late"
    assert late_run_2.state_name == "Late"


async def test_only_scheduled_runs_marked_late(
    session,
    late_run,
    pending_run,
):
    # late scheduled run is correctly marked late
    assert late_run.state.name == "Scheduled"

    await MarkLateRuns()._mark_flow_run_as_late(session, late_run)
    await session.refresh(late_run)
    assert late_run.state_name == "Late"

    # pending run cannot be marked late
    assert pending_run.state.name == "Pending"

    await MarkLateRuns()._mark_flow_run_as_late(session, pending_run)
    await session.refresh(pending_run)
    assert pending_run.state_name == "Pending"


async def test_mark_late_runs_fires_flow_run_state_change_events(
    late_run: "ORMFlowRun", session: AsyncSession
):
    previous_state_id = late_run.state_id
    assert isinstance(previous_state_id, UUID)

    await MarkLateRuns().start(loops=1)

    session.expunge_all()

    updated_flow_run = await models.flow_runs.read_flow_run(session, late_run.id)
    late_state_id = updated_flow_run.state_id
    assert isinstance(late_state_id, UUID)
    assert late_state_id != previous_state_id

    assert AssertingEventsClient.last
    assert len(AssertingEventsClient.last.events) == 1
    (event,) = AssertingEventsClient.last.events

    assert event.resource.id == f"prefect.flow-run.{late_run.id}"
    assert event.event == "prefect.flow-run.Late"
    assert event.resource["prefect.state-type"] == "SCHEDULED"
    assert event.payload == {
        "intended": {"from": "SCHEDULED", "to": "SCHEDULED"},
        "initial_state": {"type": "SCHEDULED", "name": "Scheduled"},
        "validated_state": {"type": "SCHEDULED", "name": "Late"},
    }

    # The events should use the state IDs to help track the ordering of events
    assert event.id == late_state_id
    assert event.follows == previous_state_id


async def test_mark_late_runs_ignores_missing_runs(late_run: "ORMFlowRun"):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2846"""
    # Simulate another process deleting the flow run in the middle of the service loop
    # Before the fix, this would have raised the ObjectNotFoundError
    with mock.patch("prefect.server.models.flow_runs.read_flow_run", return_value=None):
        service = MarkLateRuns()
        await service._on_start()
        try:
            await service.run_once()
        finally:
            await service._on_stop()
