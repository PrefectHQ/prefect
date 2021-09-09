import pendulum
import pytest

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.orchestration.rules import (
    OrchestrationContext,
    FlowOrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.orchestration.core_policy import WaitForScheduledTime
from prefect.orion.schemas import states


async def create_task_run_state(
    session, task_run, state_type: states.StateType, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    if (
        state_type == states.StateType.SCHEDULED
        and "scheduled_time" not in state_details
    ):
        state_details.update({"scheduled_time": pendulum.now()})

    new_state = schemas.actions.StateCreate(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    orm_state = orm.TaskRunState(
        task_run_id=task_run.id,
        **new_state.dict(shallow=True),
    )

    session.add(orm_state)
    await session.flush()
    return orm_state.as_state()


async def create_flow_run_state(
    session, flow_run, state_type: states.StateType, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    if (
        state_type == states.StateType.SCHEDULED
        and "scheduled_time" not in state_details
    ):
        state_details.update({"scheduled_time": pendulum.now()})

    new_state = schemas.actions.StateCreate(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    orm_state = orm.FlowRunState(
        flow_run_id=flow_run.id,
        **new_state.dict(shallow=True),
    )

    session.add(orm_state)
    await session.flush()
    return orm_state.as_state()


@pytest.fixture
def initialize_orchestration(
        session,
        task_run,
        flow_run,
):
    async def initializer(
        orchestration_type,
        initial_state_type,
        proposed_state_type,
        state_details=None,
    ) -> OrchestrationContext:
        if orchestration_type == "flow":
            run = flow_run
            context = FlowOrchestrationContext
            state_constructor = create_flow_run_state
        elif orchestration_type == "task":
            run = task_run
            context = TaskOrchestrationContext
            state_constructor = create_task_run_state

        initial_state = await state_constructor(
            session,
            run,
            initial_state_type,
            state_details,
        )

        proposed_state = states.State(type=proposed_state_type)

        ctx = context(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=run,
            run_id=run.id,
        )

        return ctx
    return initializer


@pytest.mark.parametrize("orchestration_type", ["task", "flow"])
class TestWaitForScheduledTimeRule:
    async def test_late_scheduled_states_just_run(
        self, orchestration_type, initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            orchestration_type,
            *intended_transition,
            {"scheduled_time": pendulum.now().subtract(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.validated_state_type == proposed_state_type

    async def test_early_scheduled_states_are_delayed(
        self, orchestration_type, initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            "flow",
            *intended_transition,
            {"scheduled_time": pendulum.now().add(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == schemas.responses.SetStateStatus.WAIT
        assert ctx.proposed_state is None
        assert abs(ctx.response_details.delay_seconds - 300) < 2

    async def test_scheduled_states_without_scheduled_times_are_bad(
        self, orchestration_type, initialize_orchestration,
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            "flow",
            *intended_transition,
        )

        with pytest.raises(ValueError):
            async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
                pass
