import contextlib
import pendulum
import pytest
from itertools import product

from prefect.orion import models
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.orchestration.core_policy import (
    CacheInsertion,
    CacheRetrieval,
    PreventTransitionsFromTerminalStates,
    RetryPotentialFailures,
    UpdateSubflowParentTask,
    WaitForScheduledTime,
)
from prefect.orion.orchestration.global_policy import (
    UpdateRunDetails,
)
from prefect.orion.orchestration.rules import ALL_ORCHESTRATION_STATES, TERMINAL_STATES
from prefect.orion.schemas import states, actions


def transition_names(transition):
    initial = f"{transition[0].name if transition[0] else None}"
    proposed = f" => {transition[1].name if transition[1] else None}"
    return initial + proposed


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestWaitForScheduledTimeRule:
    async def test_late_scheduled_states_just_run(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().subtract(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.validated_state_type == proposed_state_type

    async def test_early_scheduled_states_are_delayed(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().add(minutes=5)},
        )

        async with WaitForScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.WAIT
        assert ctx.proposed_state is None
        assert abs(ctx.response_details.delay_seconds - 300) < 2

    async def test_scheduling_rule_does_not_fire_against_other_state_types(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        scheduling_rule = WaitForScheduledTime(ctx, *intended_transition)
        async with scheduling_rule as ctx:
            pass
        assert await scheduling_rule.invalid()


class TestCachingBackendLogic:
    @pytest.mark.parametrize(
        ["expiration", "expected_status", "expected_name"],
        [
            (pendulum.now().subtract(days=1), SetStateStatus.ACCEPT, "Running"),
            (pendulum.now().add(days=1), SetStateStatus.REJECT, "Cached"),
            (None, SetStateStatus.REJECT, "Cached"),
        ],
        ids=["past", "future", "null"],
    )
    async def test_set_and_retrieve_unexpired_cached_states(
        self,
        session,
        initialize_orchestration,
        expiration,
        expected_status,
        expected_name,
    ):
        caching_policy = [CacheInsertion, CacheRetrieval]

        # this first proposed state is added to the cache table
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

        assert ctx1.response_status == SetStateStatus.ACCEPT

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

    @pytest.mark.parametrize(
        "proposed_state_type",
        set(states.StateType) - set([states.StateType.COMPLETED]),
        ids=lambda statetype: statetype.name,
    )
    async def test_only_cache_completed_states(
        self,
        session,
        initialize_orchestration,
        proposed_state_type,
    ):
        caching_policy = [CacheInsertion, CacheRetrieval]

        # this first proposed state is added to the cache table
        initial_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx1 = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_details={"cache_key": "cache-hit"},
            proposed_details={"cache_key": "cache-hit"},
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in caching_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *intended_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx2 = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_details={"cache_key": "cache-hit"},
            proposed_details={"cache_key": "cache-hit"},
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in caching_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *intended_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.ACCEPT


class TestRetryingRule:
    async def test_retry_potential_failures(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RetryPotentialFailures, UpdateRunDetails]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = await ctx.orm_run()
        run_settings = await ctx.run_settings()
        orm_run.run_count = 2
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED

    async def test_stops_retrying_eventually(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RetryPotentialFailures, UpdateRunDetails]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = await ctx.orm_run()
        run_settings = await ctx.run_settings()
        orm_run.run_count = 3
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.FAILED


async def test_update_subflow_parent_task(
    session,
    initialize_orchestration,
):
    update_subflows_policy = [UpdateSubflowParentTask]
    initial_state_type = states.StateType.RUNNING
    proposed_state_type = states.StateType.FAILED
    intended_transition = (initial_state_type, proposed_state_type)
    ctx = await initialize_orchestration(
        session,
        "flow",
        *intended_transition,
    )

    parent_flow = await models.flows.create_flow(
        session=session, flow=actions.FlowCreate(name="subflow-parent")
    )

    parent_flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=actions.FlowRunCreate(flow_id=parent_flow.id),
    )

    parent_task_run = await models.task_runs.create_task_run(
        session=session,
        task_run=actions.TaskRunCreate(
            task_key="dummy-task", flow_run_id=parent_flow_run.id
        ),
    )

    run = await ctx.orm_run()
    run.parent_task_run_id = parent_task_run.id

    async with contextlib.AsyncExitStack() as stack:
        for rule in update_subflows_policy:
            ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
        await ctx.validate_proposed_state()

    assert parent_task_run.state.type == proposed_state_type


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestTransitionsFromTerminalStatesRule:
    all_transitions = set(product(ALL_ORCHESTRATION_STATES, ALL_ORCHESTRATION_STATES))
    terminal_transitions = set(product(TERMINAL_STATES, ALL_ORCHESTRATION_STATES))
    active_transitions = all_transitions - terminal_transitions

    @pytest.mark.parametrize(
        "intended_transition", terminal_transitions, ids=transition_names
    )
    async def test_transitions_from_terminal_states_are_aborted(
        self,
        session,
        run_type,
        initialize_orchestration,
        intended_transition,
    ):
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        state_protection = PreventTransitionsFromTerminalStates(
            ctx, *intended_transition
        )

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ABORT

    @pytest.mark.parametrize(
        "intended_transition", active_transitions, ids=transition_names
    )
    async def test_all_other_transitions_are_accepted(
        self,
        session,
        run_type,
        initialize_orchestration,
        intended_transition,
    ):
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        state_protection = PreventTransitionsFromTerminalStates(
            ctx, *intended_transition
        )

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
