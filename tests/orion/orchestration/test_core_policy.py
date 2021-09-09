import contextlib
import pendulum
import pytest

from prefect.orion import schemas
from prefect.orion.schemas import responses
from prefect.orion.models import orm
from prefect.orion.orchestration.rules import (
    OrchestrationContext,
    FlowOrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.orchestration.core_policy import (
    WaitForScheduledTime,
    RetryPotentialFailures,
    CacheInsertion,
    CacheRetrieval,
)
from prefect.orion.orchestration.global_policy import (
    UpdateRunDetails,
    UpdateStateDetails,
)
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
    task_run,
    flow_run,
):
    async def initializer(
        session,
        orchestration_type,
        initial_state_type,
        proposed_state_type,
        initial_details=None,
        proposed_details=None,
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
            initial_details,
        )

        proposed_details = proposed_details if proposed_details else dict()
        psd = states.StateDetails(**proposed_details)
        proposed_state = states.State(type=proposed_state_type, state_details=psd)

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
        self,
        session,
        orchestration_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            orchestration_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().subtract(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.validated_state_type == proposed_state_type

    async def test_early_scheduled_states_are_delayed(
        self,
        session,
        orchestration_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            orchestration_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().add(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == responses.SetStateStatus.WAIT
        assert ctx.proposed_state is None
        assert abs(ctx.response_details.delay_seconds - 300) < 2

    async def test_scheduled_states_without_scheduled_times_are_bad(
        self,
        session,
        orchestration_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            orchestration_type,
            *intended_transition,
        )

        with pytest.raises(ValueError):
            async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
                pass


class TestCachingBackendLogic:
    @pytest.mark.parametrize(
        ["expiration", "expected_status", "expected_name"],
        [
            (pendulum.now().subtract(days=1), responses.SetStateStatus.ACCEPT, "Running"),
            (pendulum.now().add(days=1), responses.SetStateStatus.REJECT, "Cached"),
            (None, responses.SetStateStatus.REJECT, "Cached"),
        ],
        ids=["past", "future", "null"],
    )
    async def test_set_and_retrieve_cached_task_run_state(
        self,
        session,
        initialize_orchestration,
        expiration,
        expected_status,
        expected_name,
    ):
        caching_policy = [CacheInsertion, CacheRetrieval]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.COMPLETED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx1 = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_details={"cache_key": "cache-hit", "cache_expiration": expiration},
            proposed_details={"cache_key": "cache-hit", "cache_expiration": expiration},
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in caching_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *intended_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == responses.SetStateStatus.ACCEPT

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx2 = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_details={"cache_key": "cache-hit", "cache_expiration": expiration},
            proposed_details={"cache_key": "cache-hit", "cache_expiration": expiration},
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in caching_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *intended_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == expected_status
        assert ctx2.validated_state.name == expected_name
