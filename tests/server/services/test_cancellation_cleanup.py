import pendulum
import pytest

from prefect.server import models, schemas
from prefect.server.schemas import states
from prefect.server.services.cancellation_cleanup import CancellationCleanup

NON_TERMINAL_STATE_CONSTRUCTORS = {
    states.StateType.SCHEDULED: states.Scheduled,
    states.StateType.PENDING: states.Pending,
    states.StateType.RUNNING: states.Running,
    states.StateType.PAUSED: states.Paused,
    states.StateType.CANCELLING: states.Cancelling,
}

TERMINAL_STATE_CONSTRUCTORS = {
    states.StateType.COMPLETED: states.Completed,
    states.StateType.FAILED: states.Failed,
    states.StateType.CRASHED: states.Crashed,
    states.StateType.CANCELLED: states.Cancelled,
}

THE_PAST = pendulum.now("UTC") - pendulum.Duration(hours=5)
THE_ANCIENT_PAST = pendulum.now("UTC") - pendulum.Duration(days=100)


@pytest.fixture
async def cancelled_flow_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_PAST
            ),
        )


@pytest.fixture
async def old_cancelled_flow_run(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_ANCIENT_PAST
            ),
        )


@pytest.fixture
async def orphaned_task_run_maker(session):
    async def task_run_maker(flow_run, state_constructor):
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
async def orphaned_subflow_run_maker(session, flow):
    async def subflow_run_maker(flow_run, state_constructor):
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


async def test_all_state_types_are_tested():
    assert set(NON_TERMINAL_STATE_CONSTRUCTORS.keys()).union(
        set(TERMINAL_STATE_CONSTRUCTORS.keys())
    ) == set(states.StateType)


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_service_cleans_up_nonterminal_runs(
    session,
    cancelled_flow_run,
    orphaned_task_run_maker,
    orphaned_subflow_run_maker,
    state_constructor,
):
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]

    await CancellationCleanup(handle_signals=False).start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)

    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_service_ignores_old_cancellations(
    session,
    old_cancelled_flow_run,
    orphaned_task_run_maker,
    orphaned_subflow_run_maker,
    state_constructor,
):
    orphaned_task_run = await orphaned_task_run_maker(
        old_cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        old_cancelled_flow_run, state_constructor[1]
    )
    assert old_cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]

    await CancellationCleanup(handle_signals=False).start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)

    # tasks are ignored, but subflows will still be cancelled
    assert old_cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_service_leaves_terminal_runs_alone(
    session,
    cancelled_flow_run,
    orphaned_task_run_maker,
    orphaned_subflow_run_maker,
    state_constructor,
):
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]

    await CancellationCleanup(handle_signals=False).start(loops=1)
    await session.refresh(orphaned_task_run)
    await session.refresh(orphaned_subflow_run)

    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]
    assert orphaned_subflow_run.state.type == state_constructor[0]
