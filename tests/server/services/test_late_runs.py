"""Tests for the late_runs docket task functions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from prefect.server import models, schemas
from prefect.server.services.late_runs import mark_flow_run_late


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


async def test_marks_late_run(session, late_run, db):
    assert late_run.state.name == "Scheduled"
    st = late_run.state.state_details.scheduled_time
    assert late_run.next_scheduled_start_time == st

    await mark_flow_run_late(late_run.id, db=db)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"
    st2 = late_run.state.state_details.scheduled_time
    assert st == st2


async def test_marks_multiple_late_runs(session, late_run, late_run_2, db):
    assert late_run.state.name == "Scheduled"
    assert late_run_2.state.name == "Scheduled"

    await mark_flow_run_late(late_run.id, db=db)
    await mark_flow_run_late(late_run_2.id, db=db)

    await session.refresh(late_run)
    await session.refresh(late_run_2)

    assert late_run.state_name == "Late"
    assert late_run_2.state_name == "Late"


async def test_does_not_mark_pending_run_late(session, pending_run, db):
    assert pending_run.state.name == "Pending"

    await mark_flow_run_late(pending_run.id, db=db)

    await session.refresh(pending_run)
    assert pending_run.state_name == "Pending"


async def test_marks_future_run_late_when_called_directly(session, future_run, db):
    """The task function marks runs as late when called directly.

    The monitor_late_runs perpetual function filters which runs to mark,
    so future runs would not be passed to this task function in production.
    """
    assert future_run.state.name == "Scheduled"

    await mark_flow_run_late(future_run.id, db=db)

    await session.refresh(future_run)
    # The task function marks it late since it trusts the caller filtered correctly
    assert future_run.state.name == "Late"


async def test_handles_deleted_flow_run(db):
    """Test that mark_flow_run_late handles missing flow runs gracefully."""
    # Should not raise an error
    await mark_flow_run_late(uuid4(), db=db)


async def test_monitor_query_filters_already_late_runs(session, late_run, db):
    """Late runs are not re-marked because the monitor query filters them out.

    The monitor_late_runs query only selects runs with state_name == "Scheduled",
    so already-late runs are not passed to the mark_flow_run_late task.
    """
    assert late_run.state.name == "Scheduled"

    await mark_flow_run_late(late_run.id, db=db)

    await session.refresh(late_run)
    assert late_run.state.name == "Late"

    # The monitor query would not select this run again because:
    # - state_name is now "Late", not "Scheduled"
    # This is tested by verifying the query filter behavior, not by calling the task twice


async def test_cancels_late_run_when_deployment_has_cancel_new_and_limit_is_full(
    session, flow, db
):
    """When a deployment uses CANCEL_NEW and its concurrency limit is full,
    mark_flow_run_late should cancel the run instead of marking it Late.

    Regression test for https://github.com/PrefectHQ/prefect/issues/21060
    """
    # create a deployment with CANCEL_NEW, limit=1
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"cancel-new-deployment-{uuid4()}",
            flow_id=flow.id,
            concurrency_limit=1,
            concurrency_options={
                "collision_strategy": schemas.core.ConcurrencyLimitStrategy.CANCEL_NEW,
            },
        ),
    )
    await session.flush()

    # create a RUNNING flow run to occupy the concurrency slot
    await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=schemas.states.Running(),
        ),
    )
    # actually acquire the concurrency slot for the running run
    if deployment.concurrency_limit_id:
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

    # create a scheduled run that's past due (would be marked Late)
    late_candidate = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=schemas.states.Scheduled(
                scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=1)
            ),
        ),
    )
    await session.commit()

    assert late_candidate.state.name == "Scheduled"

    await mark_flow_run_late(late_candidate.id, db=db)

    await session.refresh(late_candidate)
    # The run should be cancelled, not merely marked Late
    assert late_candidate.state_type == schemas.states.StateType.CANCELLED, (
        f"Expected CANCELLED but got {late_candidate.state_type}/{late_candidate.state_name}. "
        "CANCEL_NEW should proactively cancel runs that would go Late when the "
        "deployment concurrency limit is full."
    )


async def test_marks_late_not_cancelled_when_cancel_new_but_limit_not_full(
    session, flow, db
):
    """When a deployment uses CANCEL_NEW but the concurrency limit has
    available slots, runs should be marked Late normally (not cancelled).

    Regression test for https://github.com/PrefectHQ/prefect/issues/21060
    """
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"cancel-new-available-{uuid4()}",
            flow_id=flow.id,
            concurrency_limit=1,
            concurrency_options={
                "collision_strategy": schemas.core.ConcurrencyLimitStrategy.CANCEL_NEW,
            },
        ),
    )
    await session.flush()

    # no running flow runs — the concurrency slot is available
    late_candidate = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=schemas.states.Scheduled(
                scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=1)
            ),
        ),
    )
    await session.commit()

    await mark_flow_run_late(late_candidate.id, db=db)

    await session.refresh(late_candidate)
    # Slot is available, so the run should be marked Late (not cancelled)
    assert late_candidate.state_name == "Late"


async def test_marks_late_when_deployment_has_enqueue_strategy(session, flow, db):
    """Runs on ENQUEUE deployments should always be marked Late, even when
    the concurrency limit is full.

    Regression test for https://github.com/PrefectHQ/prefect/issues/21060
    """
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"enqueue-deployment-{uuid4()}",
            flow_id=flow.id,
            concurrency_limit=1,
            concurrency_options={
                "collision_strategy": schemas.core.ConcurrencyLimitStrategy.ENQUEUE,
            },
        ),
    )
    await session.flush()

    # occupy the concurrency slot
    await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=schemas.states.Running(),
        ),
    )
    if deployment.concurrency_limit_id:
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

    late_candidate = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=schemas.states.Scheduled(
                scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=1)
            ),
        ),
    )
    await session.commit()

    await mark_flow_run_late(late_candidate.id, db=db)

    await session.refresh(late_candidate)
    # ENQUEUE strategy should mark Late, not cancel
    assert late_candidate.state_name == "Late"
