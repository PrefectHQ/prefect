"""Tests for the cancellation cleanup perpetual service."""

from typing import Any, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import provide_database_interface
from prefect.server.schemas import states
from prefect.server.schemas.core import Deployment, Flow, FlowRun
from prefect.server.services.cancellation_cleanup import (
    cancel_child_task_runs,
    cancel_subflow_run,
)
from prefect.types._datetime import Duration, now

NON_TERMINAL_STATE_CONSTRUCTORS: dict[states.StateType, Any] = {
    states.StateType.SCHEDULED: states.Scheduled,
    states.StateType.PENDING: states.Pending,
    states.StateType.RUNNING: states.Running,
    states.StateType.PAUSED: states.Paused,
    states.StateType.CANCELLING: states.Cancelling,
}

TERMINAL_STATE_CONSTRUCTORS: dict[states.StateType, Any] = {
    states.StateType.COMPLETED: states.Completed,
    states.StateType.FAILED: states.Failed,
    states.StateType.CRASHED: states.Crashed,
    states.StateType.CANCELLED: states.Cancelled,
}

THE_PAST = now("UTC") - Duration(hours=5)
THE_ANCIENT_PAST = now("UTC") - Duration(days=100)


@pytest.fixture
async def cancelled_flow_run(session: AsyncSession, flow: Flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_PAST
            ),
        )


@pytest.fixture
async def old_cancelled_flow_run(session: AsyncSession, flow: Flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_ANCIENT_PAST
            ),
        )


@pytest.fixture
async def orphaned_task_run_maker(session: AsyncSession):
    async def task_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            return await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a task",
                    dynamic_key="a dynamic key",
                    state=state_constructor(),
                ),
            )

    return task_run_maker


@pytest.fixture
async def orphaned_subflow_run_maker(session: AsyncSession, flow: Flow):
    async def subflow_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            virtual_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a virtual task",
                    dynamic_key="a virtual dynamic key",
                    state=state_constructor(),
                ),
            )

            return await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    parent_task_run_id=virtual_task.id,
                    state=state_constructor(),
                    end_time=THE_PAST,
                ),
            )

    return subflow_run_maker


@pytest.fixture
async def orphaned_subflow_run_from_deployment_maker(
    session: AsyncSession, flow: Flow, deployment: Deployment
):
    async def subflow_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            virtual_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a virtual task for subflow from deployment",
                    dynamic_key="a virtual dynamic key for subflow from deployment",
                    state=state_constructor(),
                ),
            )

            return await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    parent_task_run_id=virtual_task.id,
                    state=state_constructor(),
                    end_time=THE_PAST,
                    deployment_id=deployment.id,
                    infrastructure_pid="my-pid-42",
                ),
            )

    return subflow_run_maker


async def test_all_state_types_are_tested():
    assert set(NON_TERMINAL_STATE_CONSTRUCTORS.keys()).union(
        set(TERMINAL_STATE_CONSTRUCTORS.keys())
    ) == set(states.StateType)


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_child_task_runs_cancels_nonterminal_tasks(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_child_task_runs cancels non-terminal task runs."""
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_child_task_runs(cancelled_flow_run.id, db=db)

    await session.refresh(orphaned_task_run)
    assert orphaned_task_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_cancels_nonterminal_subflows(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_subflow_run cancels non-terminal subflow runs."""
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    assert orphaned_subflow_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_sets_cancelling_for_deployment_subflows(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_from_deployment_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that subflows from deployments get CANCELLING state (not CANCELLED)."""
    orphaned_subflow_run = await orphaned_subflow_run_from_deployment_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    # Subflows from deployments should be set to CANCELLING (not CANCELLED)
    # so the infrastructure can be properly cleaned up
    assert orphaned_subflow_run.state.type == "CANCELLING"


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_child_task_runs_leaves_terminal_tasks_alone(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_child_task_runs doesn't modify terminal task runs."""
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_child_task_runs(cancelled_flow_run.id, db=db)

    await session.refresh(orphaned_task_run)
    # Terminal states should not be changed
    assert orphaned_task_run.state.type == state_constructor[0]


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_leaves_terminal_subflows_alone(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_subflow_run doesn't modify terminal subflow runs."""
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    # Terminal states should not be changed
    assert orphaned_subflow_run.state.type == state_constructor[0]


async def test_cancel_subflow_run_ignores_non_cancelled_parents(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_subflow_run doesn't cancel subflows whose parent isn't cancelled."""
    # Create a running parent flow run (not cancelled)
    async with session.begin():
        parent_flow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=states.Running(),
            ),
        )
        virtual_task = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=parent_flow.id,
                task_key="virtual task",
                dynamic_key="dynamic key",
                state=states.Running(),
            ),
        )
        subflow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                parent_task_run_id=virtual_task.id,
                state=states.Running(),
            ),
        )

    assert parent_flow.state.type == "RUNNING"
    assert subflow.state.type == "RUNNING"

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(subflow.id, db=db)

    await session.refresh(subflow)
    # Subflow should still be running since parent isn't cancelled
    assert subflow.state.type == "RUNNING"


async def test_cancel_child_task_runs_handles_deleted_flow_run(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_child_task_runs handles the case where flow run was deleted."""
    from uuid import uuid4

    # Call with a non-existent flow run ID - should not raise
    db = provide_database_interface()
    await cancel_child_task_runs(uuid4(), db=db)


async def test_cancel_subflow_run_handles_deleted_flow_run(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_subflow_run handles the case where flow run was deleted."""
    from uuid import uuid4

    # Call with a non-existent flow run ID - should not raise
    db = provide_database_interface()
    await cancel_subflow_run(uuid4(), db=db)
