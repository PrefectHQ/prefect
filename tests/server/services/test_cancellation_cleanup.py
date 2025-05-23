from typing import Any, Callable, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database.orm_models import ORMFlow, ORMFlowRun
from prefect.server.schemas import states
from prefect.server.schemas.core import Deployment, Flow, FlowRun
from prefect.server.services.cancellation_cleanup import CancellationCleanup
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
async def test_service_cleans_up_nonterminal_runs(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    orphaned_subflow_run_maker: Callable[..., Any],
    orphaned_subflow_run_from_deployment_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run_from_deployment = (
        await orphaned_subflow_run_from_deployment_maker(
            cancelled_flow_run, state_constructor[1]
        )
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]
    assert orphaned_subflow_run_from_deployment.state.type == state_constructor[0]

    await CancellationCleanup().start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)
    await session.refresh(orphaned_subflow_run_from_deployment)

    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run_from_deployment.state.type == "CANCELLING"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_service_ignores_old_cancellations(
    session: AsyncSession,
    old_cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    orphaned_subflow_run_maker: Callable[..., Any],
    orphaned_subflow_run_from_deployment_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    orphaned_task_run = await orphaned_task_run_maker(
        old_cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        old_cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run_from_deployment = (
        await orphaned_subflow_run_from_deployment_maker(
            old_cancelled_flow_run, state_constructor[1]
        )
    )
    assert old_cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]
    assert orphaned_subflow_run_from_deployment.state.type == state_constructor[0]

    await CancellationCleanup().start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)
    await session.refresh(orphaned_subflow_run_from_deployment)

    # tasks are ignored, but subflows will still be cancelled
    assert old_cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run_from_deployment.state.type == "CANCELLING"


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_service_leaves_terminal_runs_alone(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    orphaned_subflow_run_maker: Callable[..., Any],
    orphaned_subflow_run_from_deployment_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run_from_deployment = (
        await orphaned_subflow_run_from_deployment_maker(
            cancelled_flow_run, state_constructor[1]
        )
    )

    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]
    assert orphaned_subflow_run_from_deployment.state.type == state_constructor[0]

    await CancellationCleanup().start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)
    await session.refresh(orphaned_subflow_run_from_deployment)

    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]
    assert orphaned_subflow_run_from_deployment.state.type == state_constructor[0]


async def test_service_works_with_partial_flow_run_objects(
    session: AsyncSession,
    flow: Flow,
    deployment: Deployment,
):
    """
    Test that the cancellation cleanup service works correctly with partial FlowRun objects.
    This verifies that selecting only specific columns in the query doesn't break functionality.
    """
    # Create a parent flow run and task run
    async with session.begin():
        parent_flow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=states.Cancelled(),
                end_time=THE_PAST,
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

    # Create subflows in different states
    async with session.begin():
        subflow_with_deployment = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                parent_task_run_id=virtual_task.id,
                state=states.Running(),
                deployment_id=deployment.id,
            ),
        )
        subflow_without_deployment = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                parent_task_run_id=virtual_task.id,
                state=states.Running(),
            ),
        )

    # Run the cleanup service
    await CancellationCleanup().start(loops=1)

    # Refresh states
    async with session.begin():
        await session.refresh(subflow_with_deployment)
        await session.refresh(subflow_without_deployment)

    # Verify correct state transitions with partial objects
    assert subflow_with_deployment.state.type == states.StateType.CANCELLING
    assert subflow_without_deployment.state.type == states.StateType.CANCELLED


@pytest.fixture
async def many_cancelled_runs(
    session: AsyncSession, flow: ORMFlow
) -> Sequence[ORMFlowRun]:
    runs: list[ORMFlowRun] = []
    async with session.begin():
        for i in range(10):
            runs.append(
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id, state=states.Cancelled(), end_time=THE_PAST
                    ),
                )
            )
    return runs


async def test_service_does_a_finite_amount_of_work(
    session: AsyncSession, many_cancelled_runs: Sequence[ORMFlowRun]
):
    """Regression test for PrefectHQ/prefect#18005, where the CancellationCleanup
    service can get stuck in an infinite loop if more than the batch size of runs
    are cancelled"""

    service = CancellationCleanup()
    service.batch_size = 5
    assert len(many_cancelled_runs) > service.batch_size

    await service.start(loops=1)
