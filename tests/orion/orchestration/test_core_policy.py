import contextlib
import random
from itertools import product
from unittest import mock

import pendulum
import pytest

from prefect.orion import schemas
from prefect.orion.models import concurrency_limits
from prefect.orion.orchestration.core_policy import (
    CacheInsertion,
    CacheRetrieval,
    PreventTransitionsFromTerminalStates,
    ReleaseTaskConcurrencySlots,
    RenameReruns,
    RetryFailedFlows,
    RetryFailedTasks,
    SecureTaskConcurrencySlots,
    WaitForScheduledTime,
)
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
)
from prefect.orion.schemas import actions, filters, states
from prefect.orion.schemas.responses import SetStateStatus
from prefect.testing.utilities import AsyncMock

# Convert constants from sets to lists for deterministic ordering of tests
ALL_ORCHESTRATION_STATES = list(
    sorted(ALL_ORCHESTRATION_STATES, key=lambda item: str(item))
    # Set the key to sort the `None` state
)
TERMINAL_STATES = list(sorted(TERMINAL_STATES))


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
        # Include all state types but COMPLETED; cast to sorted list for determinism
        list(sorted(set(states.StateType) - set([states.StateType.COMPLETED]))),
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


class TestFlowRetryingRule:
    async def test_retries(
        self,
        session,
        initialize_orchestration,
        monkeypatch,
    ):
        now = pendulum.now()
        monkeypatch.setattr("pendulum.now", lambda *args: now)

        failed_task_runs = [
            mock.Mock(id="task_run_001"),
            mock.Mock(id="task_run_002"),
        ]
        read_task_runs = AsyncMock(side_effect=lambda *args, **kwargs: failed_task_runs)
        monkeypatch.setattr(
            "prefect.orion.models.task_runs.read_task_runs", read_task_runs
        )
        set_task_run_state = AsyncMock()
        monkeypatch.setattr(
            "prefect.orion.models.task_runs.set_task_run_state", set_task_run_state
        )

        retry_policy = [RetryFailedFlows]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.run_count = 1
        ctx.run_settings.retries = 1

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        # When retrying a flow any failed tasks should be set to AwaitingRetry
        read_task_runs.assert_awaited_once_with(
            session,
            flow_run_filter=filters.FlowRunFilter(id={"any_": [ctx.run.id]}),
            task_run_filter=filters.TaskRunFilter(state={"type": {"any_": ["FAILED"]}}),
        )
        set_task_run_state.assert_has_awaits(
            [
                mock.call(
                    session,
                    "task_run_001",
                    state=states.AwaitingRetry(scheduled_time=now),
                    force=True,
                ),
                mock.call(
                    session,
                    "task_run_002",
                    state=states.AwaitingRetry(scheduled_time=now),
                    force=True,
                ),
            ]
        )

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED

    async def test_stops_retrying_eventually(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RetryFailedFlows]
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.run_count = 2
        ctx.run_settings.retries = 1

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state_type == states.StateType.FAILED


class TestTaskRetryingRule:
    async def test_retry_potential_failures(
        self,
        session,
        initialize_orchestration,
    ):
        retry_policy = [RetryFailedTasks]
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
        run_settings.retries = 2

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
        retry_policy = [RetryFailedTasks]
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
        run_settings.retries = 2

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
        run_settings.retries = 2

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
        run_settings.retries = 2

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
        run_settings.retries = 2

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

    # Cast to sorted lists for deterministic ordering.
    # Sort as strings to handle `None`.
    active_transitions = list(
        sorted(all_transitions - terminal_transitions, key=lambda item: str(item))
    )
    all_transitions = list(sorted(all_transitions, key=lambda item: str(item)))
    terminal_transitions = list(
        sorted(terminal_transitions, key=lambda item: str(item))
    )

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
        await self.create_concurrency_limit(session, "some tag", 1)
        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        # before any runs, no active concurrency slots are in use
        assert (await self.count_concurrency_slots(session, "some tag")) == 0

        task1_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["some tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        # a first task run against a concurrency limited tag will be accepted
        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT

        task2_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["some tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_running_ctx = await stack.enter_async_context(
                    rule(task2_running_ctx, *running_transition)
                )
            await task2_running_ctx.validate_proposed_state()

        # the first task hasn't completed, so the concurrently running second task is
        # told to wait
        assert task2_running_ctx.response_status == SetStateStatus.WAIT

        # the number of slots occupied by active runs is equal to the concurrency limit
        assert (await self.count_concurrency_slots(session, "some tag")) == 1

        task1_completed_ctx = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=task1_running_ctx.run,
            run_tags=["some tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_completed_ctx = await stack.enter_async_context(
                    rule(task1_completed_ctx, *completed_transition)
                )
            await task1_completed_ctx.validate_proposed_state()

        # the first task run will transition into a completed state, yielding a
        # concurrency slot
        assert task1_completed_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "some tag")) == 0

        # the second task tries to run again, this time the transition will be accepted
        # now that a concurrency slot has been freed
        task2_run_retry_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_override=task2_running_ctx.run,
            run_tags=["some tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_run_retry_ctx = await stack.enter_async_context(
                    rule(task2_run_retry_ctx, *running_transition)
                )
            await task2_run_retry_ctx.validate_proposed_state()

        assert task2_run_retry_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "some tag")) == 1

    async def test_concurrency_limiting_aborts_transitions_with_zero_limit(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        # concurrency limits of 0 will deadlock without a short-circuit
        await self.create_concurrency_limit(session, "the worst limit", 0)
        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["the worst limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        # instead of a WAIT response, Orion should direct the client to ABORT
        assert ctx.response_status == SetStateStatus.ABORT

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
            ReleaseTaskConcurrencySlots,
            StateMutatingRule,
        ]

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["a nice little limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert (await self.count_concurrency_slots(session, "a nice little limit")) == 0

    async def test_one_run_wont_consume_multiple_slots(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):

        await self.create_concurrency_limit(session, "a generous limit", 10)

        concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["a generous limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "a generous limit")) == 1

        duplicate_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_override=ctx.run,
            run_tags=["a generous limit"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                duplicate_ctx = await stack.enter_async_context(
                    rule(duplicate_ctx, *running_transition)
                )
            await duplicate_ctx.validate_proposed_state()

        # we might want to protect against a identical transitions from the same run
        # from being accepted, but this orchestration rule is the wrong place to do it
        assert duplicate_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "a generous limit")) == 1

    async def test_concurrency_race_condition_new_tags_arent_double_counted(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "primary tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        task1_running_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT

        await self.create_concurrency_limit(session, "secondary tag", 1)

        # the concurrency limit on "secondary tag" was created after the first task
        # started running, so no runs against the second limit were counted
        assert (await self.count_concurrency_slots(session, "primary tag")) == 1
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 0

        task2_running_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_running_ctx = await stack.enter_async_context(
                    rule(task2_running_ctx, *running_transition)
                )
            await task2_running_ctx.validate_proposed_state()

        assert task2_running_ctx.response_status == SetStateStatus.ACCEPT

        # both concurrency limits have an active slot consumed by the second task
        assert (await self.count_concurrency_slots(session, "primary tag")) == 2
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 1

        task1_completed_ctx = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=task1_running_ctx.run,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_completed_ctx = await stack.enter_async_context(
                    rule(task1_completed_ctx, *completed_transition)
                )
            await task1_completed_ctx.validate_proposed_state()

        # the first task completes, but despite having tags associated with both
        # concurrency limits, it only releases a concurrency slot from the first tag as
        # the task entered a running state before the second limit was created
        assert task1_completed_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "primary tag")) == 1
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 1

        task2_completed_ctx = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=task2_running_ctx.run,
            run_tags=["primary tag", "secondary tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_completed_ctx = await stack.enter_async_context(
                    rule(task2_completed_ctx, *completed_transition)
                )
            await task2_completed_ctx.validate_proposed_state()

        # after the second task completes, all concurrency slots are released
        assert task2_completed_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "primary tag")) == 0
        assert (await self.count_concurrency_slots(session, "secondary tag")) == 0

    async def test_concurrency_race_condition_deleted_tags_dont_impact_execution(
        self, session, run_type, initialize_orchestration
    ):
        await self.create_concurrency_limit(session, "big limit", 2)
        await self.create_concurrency_limit(session, "small limit", 1)

        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        task1_running_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["big limit", "small limit"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "small limit")) == 1

        task2_running_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["big limit", "small limit"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_running_ctx = await stack.enter_async_context(
                    rule(task2_running_ctx, *running_transition)
                )
            await task2_running_ctx.validate_proposed_state()

        # the small limit was hit, preventing the transition
        assert task2_running_ctx.response_status == SetStateStatus.WAIT

        # removing the small limit should allow runs again
        await self.delete_concurrency_limit(session, "small limit")

        task3_running_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_tags=["big limit", "small limit"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task3_running_ctx = await stack.enter_async_context(
                    rule(task3_running_ctx, *running_transition)
                )
            await task3_running_ctx.validate_proposed_state()

        assert task3_running_ctx.response_status == SetStateStatus.ACCEPT

    async def test_concurrency_race_condition_limit_increases_dont_impact_execution(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "changing limit", 1)

        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        task1_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["changing limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT

        await self.create_concurrency_limit(session, "changing limit", 2)

        task2_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["changing limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_running_ctx = await stack.enter_async_context(
                    rule(task2_running_ctx, *running_transition)
                )
            await task2_running_ctx.validate_proposed_state()

        assert task2_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "changing limit")) == 2

    async def test_concurrency_race_condition_limit_decreases_impact_new_runs(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "shrinking limit", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        task1_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shrinking limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT

        # lowering the limit to 1 will prevent any more runs from being submitted
        await self.create_concurrency_limit(session, "shrinking limit", 1)

        task2_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shrinking limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task2_running_ctx = await stack.enter_async_context(
                    rule(task2_running_ctx, *running_transition)
                )
            await task2_running_ctx.validate_proposed_state()

        assert task2_running_ctx.response_status == SetStateStatus.WAIT
        assert (await self.count_concurrency_slots(session, "shrinking limit")) == 1

    async def test_concurrency_race_condition_limit_decreases_dont_impact_existing_runs(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "shrinking limit", 2)

        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        task1_running_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shrinking limit"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(task1_running_ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT

        # even if the limit is lowered to 0, the existing run can complete
        await self.create_concurrency_limit(session, "shrinking limit", 0)
        assert (await self.count_concurrency_slots(session, "shrinking limit")) == 1

        task1_completed_ctx = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=task1_running_ctx.run,
            run_tags=["shrinking limit"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_completed_ctx = await stack.enter_async_context(
                    rule(task1_completed_ctx, *completed_transition)
                )
            await task1_completed_ctx.validate_proposed_state()

        # the concurrency slot is released as expected
        assert task1_completed_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "shrinking limit")) == 0
