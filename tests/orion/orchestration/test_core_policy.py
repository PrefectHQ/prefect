import contextlib
import pendulum
import pytest
import random

from itertools import product

from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.orchestration.core_policy import (
    CacheInsertion,
    CacheRetrieval,
    PreventTransitionsFromTerminalStates,
    RenameReruns,
    RetryPotentialFailures,
    ReturnTaskConcurrencySlots,
    SecureTaskConcurrencySlots,
    WaitForScheduledTime,
)

from prefect.orion import schemas
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
)
from prefect.orion.models import concurrency_limits
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
        retry_policy = [RetryPotentialFailures]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = ctx.run
        run_settings = ctx.run_settings
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
        retry_policy = [RetryPotentialFailures]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = ctx.run
        run_settings = ctx.run_settings
        orm_run.run_count = 3
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.FAILED


class TestRenameRetryingStates:
    async def test_rerun_states_get_renamed(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RenameReruns]
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = ctx.run
        run_settings = ctx.run_settings
        orm_run.run_count = 2
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.RUNNING
        assert ctx.validated_state.name == "Rerunning"

    async def test_retried_states_get_renamed(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RenameReruns]
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        ctx.initial_state.name = "AwaitingRetry"

        orm_run = ctx.run
        run_settings = ctx.run_settings
        orm_run.run_count = 2
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.RUNNING
        assert ctx.validated_state.name == "Retrying"

    async def test_no_rename_on_first_run(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RenameReruns]
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
        )

        orm_run = ctx.run
        run_settings = ctx.run_settings
        orm_run.run_count = 0
        run_settings.max_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.RUNNING
        assert ctx.validated_state.name == "Running"


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


@pytest.mark.parametrize("run_type", ["task"])
class TestTaskConcurrencyLimits:
    async def create_concurrency_limit(self, session, tag, limit):
        cl_create = actions.ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=limit,
        ).dict(json_compatible=True)

        cl_model = schemas.core.ConcurrencyLimit(**cl_create)

        await concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=cl_model
        )

    async def delete_concurrency_limit(self, session, tag):
        await concurrency_limits.delete_concurrency_limit_by_tag(session, tag)

    async def count_concurrency_slots(self, session, tag):
        return len(
            (
                await concurrency_limits.read_concurrency_limit_by_tag(session, tag)
            ).active_slots
        )

    async def read_concurrency_slots(self, session, tag):
        return (
            await concurrency_limits.read_concurrency_limit_by_tag(session, tag)
        ).active_slots

    async def test_basic_concurrency_limiting(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "test_tag", 1)
        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        ctx2 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.WAIT

        assert (await self.count_concurrency_slots(session, "test_tag")) == 1

        ctx3 = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=ctx1.run,
            run_tags=["test_tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx3 = await stack.enter_async_context(
                    rule(ctx3, *completed_transition)
                )
            await ctx3.validate_proposed_state()

        assert ctx3.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "test_tag")) == 0

        ctx4 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_override=ctx2.run,
            run_tags=["test_tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx4 = await stack.enter_async_context(rule(ctx4, *running_transition))
            await ctx4.validate_proposed_state()

        assert ctx4.response_status == SetStateStatus.ACCEPT

    async def test_concurrency_limiting_aborts_transitions_with_zero_limit(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "the worst limit", 0)
        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["the worst limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ABORT

    async def test_returning_concurrency_slots_on_fizzle(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                mutated_state = proposed_state.copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {initial_state.type, proposed_state.type}
                    )
                )
                await self.reject_transition(
                    mutated_state, reason="gotta fizzle some rules, for fun"
                )

            async def after_transition(self, initial_state, validated_state, context):
                pass

            async def cleanup(self, initial_state, validated_state, context):
                pass

        await self.create_concurrency_limit(session, "a nice little limit", 1)

        concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReturnTaskConcurrencySlots,
            StateMutatingRule,
        ]

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["a nice little limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.REJECT
        assert (await self.count_concurrency_slots(session, "a nice little limit")) == 0

    async def test_concurrency_race_condition_new_tags_arent_double_counted(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "primary tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx1 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        await self.create_concurrency_limit(session, "secondary tag", 1)

        assert (await self.count_concurrency_slots(session, "primary tag")) == 1
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 0

        ctx2 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.ACCEPT

        assert (await self.count_concurrency_slots(session, "primary tag")) == 2
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 1

        ctx3 = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=ctx1.run,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx3 = await stack.enter_async_context(
                    rule(ctx3, *completed_transition)
                )
            await ctx3.validate_proposed_state()

        assert ctx3.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "primary tag")) == 1
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 1

        ctx4 = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=ctx2.run,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx4 = await stack.enter_async_context(
                    rule(ctx4, *completed_transition)
                )
            await ctx4.validate_proposed_state()

        assert ctx4.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "primary tag")) == 1
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 0

    async def test_concurrency_race_condition_deleted_tags_dont_impact_execution(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "primary tag", 2)
        await self.create_concurrency_limit(session, "secondary tag", 1)

        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx1 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 1

        ctx2 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.WAIT

        await self.delete_concurrency_limit(session, "secondary tag")

        ctx3 = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx3 = await stack.enter_async_context(rule(ctx3, *running_transition))
            await ctx3.validate_proposed_state()

        assert ctx3.response_status == SetStateStatus.ACCEPT

    async def test_concurrency_race_condition_limit_increases_dont_impact_execution(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "test_tag", 1)

        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        await self.create_concurrency_limit(session, "test_tag", 2)

        ctx2 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "test_tag")) == 2

    async def test_concurrency_race_condition_limit_decreases_impact_new_runs(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "test_tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        await self.create_concurrency_limit(session, "test_tag", 1)

        ctx2 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.WAIT
        assert (await self.count_concurrency_slots(session, "test_tag")) == 1

    async def test_concurrency_race_condition_limit_decreases_dont_impact_existing_runs(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "test_tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReturnTaskConcurrencySlots]

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["test_tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "test_tag")) == 1

        await self.create_concurrency_limit(session, "test_tag", 1)

        ctx2 = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=ctx1.run,
            run_tags=["test_tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(
                    rule(ctx2, *completed_transition)
                )
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "test_tag")) == 0
