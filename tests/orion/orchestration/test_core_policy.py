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
def run(request, task_run, flow_run):
    if request.param == "task_run":
        return task_run
    elif request.param == "flow_run":
        return flow_run
    raise ValueError(f"Text fixture got bad param: {request.param!r}")


@pytest.mark.parametrize(
    ["context", "state_constructor", "run"],
    [
        (
            FlowOrchestrationContext,
            create_flow_run_state,
            "flow_run",
        ),
        (
            TaskOrchestrationContext,
            create_task_run_state,
            "task_run",
        ),
    ],
    indirect=["run"],
)
class TestWaitForScheduledTimeRule:
    async def test_late_scheduled_states_just_run(
        self, session, run, context, state_constructor
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_state = await state_constructor(
            session,
            run,
            initial_state_type,
            {"scheduled_time": pendulum.now().subtract(minutes=5)},
        )

        proposed_state = states.State(type=proposed_state_type)

        ctx = context(
            initial_state=scheduled_state,
            proposed_state=proposed_state,
            session=session,
            run=run,
            run_id=run.id,
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.validated_state_type == proposed_state_type

    async def test_early_scheduled_states_are_delayed(
        self, session, run, context, state_constructor
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_state = await state_constructor(
            session,
            run,
            initial_state_type,
            {"scheduled_time": pendulum.now().add(minutes=5)},
        )

        proposed_state = states.State(type=proposed_state_type)

        ctx = context(
            initial_state=scheduled_state,
            proposed_state=proposed_state,
            session=session,
            run=run,
            run_id=run.id,
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

            assert ctx.response_status == schemas.responses.SetStateStatus.WAIT
            assert ctx.proposed_state is None
            assert abs(ctx.response_details.delay_seconds - 300) < 2

    async def test_scheduled_states_without_scheduled_times_are_bad(
        self, session, run, context, state_constructor
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        not_a_scheduled_state = await state_constructor(
            session,
            run,
            initial_state_type,
        )
        proposed_state = states.State(type=proposed_state_type)

        ctx = OrchestrationContext(
            initial_state=not_a_scheduled_state,
            proposed_state=proposed_state,
            session=session,
            run=run,
            run_id=run.id,
        )

        with pytest.raises(ValueError):
            async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
                pass
