import contextlib
import math
import random
from itertools import combinations_with_replacement, product
from unittest import mock
from uuid import uuid4

import pendulum
import pytest

from prefect.server import schemas
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models import concurrency_limits
from prefect.server.orchestration.core_policy import (
    CacheInsertion,
    CacheRetrieval,
    CopyScheduledTime,
    HandleCancellingStateTransitions,
    HandleFlowTerminalStateTransitions,
    HandlePausingFlows,
    HandleResumingPausedFlows,
    HandleTaskTerminalStateTransitions,
    PreventRedundantTransitions,
    PreventRunningTasksFromStoppedFlows,
    ReleaseTaskConcurrencySlots,
    RenameReruns,
    RetryFailedFlows,
    RetryFailedTasks,
    SecureTaskConcurrencySlots,
    UpdateFlowRunTrackerOnTasks,
    WaitForScheduledTime,
)
from prefect.server.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
)
from prefect.server.schemas import actions, states
from prefect.server.schemas.responses import SetStateStatus
from prefect.testing.utilities import AsyncMock

# Convert constants from sets to lists for deterministic ordering of tests
ALL_ORCHESTRATION_STATES = list(
    sorted(ALL_ORCHESTRATION_STATES, key=lambda item: str(item))
    # Set the key to sort the `None` state
)
CANONICAL_STATES = list(states.StateType)
TERMINAL_STATES = list(sorted(TERMINAL_STATES))


def transition_names(transition):
    initial = f"{transition[0].name if transition[0] else None}"
    proposed = f" => {transition[1].name if transition[1] else None}"
    return initial + proposed


@pytest.fixture
def fizzling_rule():
    class FizzlingRule(BaseOrchestrationRule):
        FROM_STATES = ALL_ORCHESTRATION_STATES
        TO_STATES = ALL_ORCHESTRATION_STATES

        async def before_transition(self, initial_state, proposed_state, context):
            # this rule mutates the proposed state type, but won't fizzle itself upon exiting
            mutated_state = proposed_state.copy()
            mutated_state.type = random.choice(
                list(set(states.StateType) - {initial_state.type, proposed_state.type})
            )
            await self.reject_transition(mutated_state, reason="for testing, of course")

    return FizzlingRule


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestWaitForScheduledTimeRule:
    @pytest.mark.parametrize(
        "initial_state_type", [states.StateType.SCHEDULED, states.StateType.PENDING]
    )
    async def test_running_after_scheduled_start_time_is_not_delayed(
        self,
        session,
        run_type,
        initialize_orchestration,
        initial_state_type,
    ):
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

    @pytest.mark.parametrize(
        "initial_state_type", [states.StateType.SCHEDULED, states.StateType.PENDING]
    )
    async def test_running_before_scheduled_start_time_is_delayed(
        self,
        session,
        run_type,
        initialize_orchestration,
        initial_state_type,
    ):
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

    @pytest.mark.parametrize(
        "proposed_state_type",
        [
            states.StateType.COMPLETED,
            states.StateType.FAILED,
            states.StateType.CANCELLED,
            states.StateType.CRASHED,
        ],
    )
    async def test_scheduling_rule_does_not_fire_against_other_state_types(
        self,
        session,
        run_type,
        initialize_orchestration,
        proposed_state_type,
    ):
        initial_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().add(minutes=5)},
        )

        scheduling_rule = WaitForScheduledTime(ctx, *intended_transition)
        async with scheduling_rule as ctx:
            pass
        assert await scheduling_rule.invalid()


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestCopyScheduledTime:
    async def test_scheduled_time_copied_from_scheduled_to_pending(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.PENDING
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_time = pendulum.now().subtract(minutes=5)

        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            initial_details={"scheduled_time": scheduled_time},
        )

        async with CopyScheduledTime(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.validated_state_type == proposed_state_type
        assert ctx.validated_state.state_details.scheduled_time == scheduled_time

    @pytest.mark.parametrize(
        "proposed_state_type",
        [
            states.StateType.COMPLETED,
            states.StateType.FAILED,
            states.StateType.CANCELLED,
            states.StateType.CRASHED,
            states.StateType.RUNNING,
        ],
    )
    async def test_scheduled_time_not_copied_for_other_transitions(
        self,
        session,
        run_type,
        initialize_orchestration,
        proposed_state_type,
    ):
        initial_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            initial_details={"scheduled_time": pendulum.now().add(minutes=5)},
        )

        scheduling_rule = CopyScheduledTime(ctx, *intended_transition)
        async with scheduling_rule as ctx:
            await ctx.validate_proposed_state()

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

    async def test_cache_insertion_requires_validated_state(
        self,
        session,
        initialize_orchestration,
    ):
        """Regression test for the bug observed when exiting the CacheInsertion
        rule after a database error that prevented committing the validated state"""
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.COMPLETED
        intended_transition = (initial_state_type, proposed_state_type)
        expiration = pendulum.now().subtract(days=1)

        ctx1 = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_details={"cache_key": "cache-hit", "cache_expiration": expiration},
            proposed_details={"cache_key": "cache-hit", "cache_expiration": expiration},
        )

        with pytest.raises(ValueError, match="this better be mine"):
            async with contextlib.AsyncExitStack() as stack:
                ctx1 = await stack.enter_async_context(
                    CacheInsertion(ctx1, *intended_transition)
                )
                # Simulate an exception (for example, a database error) that happens
                # within the context manager; when this happens, we've observed the
                # CacheInsertion to raise:
                #
                #   AttributeError: 'NoneType' object has no attribute 'state_details'
                #
                # because the `validated_state` passed to its after_transition
                # handler is None
                raise ValueError("this better be mine")

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
            "prefect.server.models.task_runs.read_task_runs", read_task_runs
        )
        set_task_run_state = AsyncMock()
        monkeypatch.setattr(
            "prefect.server.models.task_runs.set_task_run_state", set_task_run_state
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


class TestManualFlowRetries:
    async def test_cannot_manual_retry_without_awaitingretry_state_name(
        self,
        session,
        initialize_orchestration,
    ):
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.name = "NotAwaitingRetry"
        ctx.run.run_count = 2
        ctx.run.deployment_id = uuid4()
        ctx.run_settings.retries = 1

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ABORT
        assert ctx.run.run_count == 2

    async def test_cannot_manual_retry_without_deployment(
        self,
        session,
        initialize_orchestration,
    ):
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
            flow_retries=1,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ABORT
        assert ctx.run.run_count == 2

    async def test_manual_retrying_works_even_when_exceeding_max_retries(
        self,
        session,
        initialize_orchestration,
    ):
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
            flow_retries=1,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.deployment_id = uuid4()
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.run.run_count == 2

    async def test_manual_retrying_bypasses_terminal_state_protection(
        self,
        session,
        initialize_orchestration,
    ):
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
            flow_retries=10,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.deployment_id = uuid4()
        ctx.run.run_count = 3

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.run.run_count == 3


class TestUpdatingFlowRunTrackerOnTasks:
    @pytest.mark.parametrize(
        "flow_run_count,initial_state_type",
        list(product((5, 42), ALL_ORCHESTRATION_STATES)),
    )
    async def test_task_runs_track_corresponding_flow_runs(
        self,
        session,
        initialize_orchestration,
        flow_run_count,
        initial_state_type,
    ):
        update_policy = [
            UpdateFlowRunTrackerOnTasks,
        ]
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_run_count=flow_run_count,
        )

        flow_run = await ctx.flow_run()
        assert flow_run.run_count == flow_run_count
        ctx.run.flow_run_run_count = 1

        async with contextlib.AsyncExitStack() as stack:
            for rule in update_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.run.flow_run_run_count == flow_run_count

    async def test_task_run_tracking_raises_informative_errors_on_missing_flow_runs(
        self,
        session,
        initialize_orchestration,
        monkeypatch,
    ):
        update_policy = [
            UpdateFlowRunTrackerOnTasks,
        ]
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_run_count=42,
        )

        flow_run = await ctx.flow_run()
        assert flow_run.run_count == 42
        ctx.run.flow_run_run_count = 1

        async def missing_flow_run(self):
            return None

        with pytest.raises(ObjectNotFoundError, match="Unable to read flow run"):
            async with contextlib.AsyncExitStack() as stack:
                for rule in update_policy:
                    ctx = await stack.enter_async_context(
                        rule(ctx, *intended_transition)
                    )
                    monkeypatch.setattr(
                        "prefect.server.orchestration.rules.TaskOrchestrationContext.flow_run",
                        missing_flow_run,
                    )

        assert (
            ctx.run.flow_run_run_count == 1
        ), "The run count should not be updated if the flow run is missing"


class TestPermitRerunningFailedTaskRuns:
    async def test_bypasses_terminal_state_rule_if_flow_is_retrying(
        self,
        session,
        initialize_orchestration,
    ):
        rerun_policy = [
            HandleTaskTerminalStateTransitions,
            UpdateFlowRunTrackerOnTasks,
        ]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_retries=10,
        )
        flow_run = await ctx.flow_run()
        flow_run.run_count = 4
        ctx.run.flow_run_run_count = 2
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in rerun_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.run.run_count == 0
        assert ctx.proposed_state.name == "Retrying"
        assert (
            ctx.run.flow_run_run_count == 4
        ), "Orchestration should update the flow run run count tracker"

    async def test_cannot_bypass_terminal_state_rule_if_exceeding_flow_runs(
        self,
        session,
        initialize_orchestration,
    ):
        rerun_policy = [
            HandleTaskTerminalStateTransitions,
            UpdateFlowRunTrackerOnTasks,
        ]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_retries=10,
        )
        flow_run = await ctx.flow_run()
        flow_run.run_count = 3
        ctx.run.flow_run_run_count = 3
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in rerun_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ABORT
        assert ctx.run.run_count == 2
        assert ctx.proposed_state is None
        assert ctx.run.flow_run_run_count == 3

    async def test_bypasses_terminal_state_rule_if_configured_automatic_retries_is_exceeded(
        self,
        session,
        initialize_orchestration,
    ):
        # this functionality enables manual retries to occur even if all automatic
        # retries have been consumed

        rerun_policy = [
            HandleTaskTerminalStateTransitions,
            UpdateFlowRunTrackerOnTasks,
        ]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_retries=1,
        )
        flow_run = await ctx.flow_run()
        flow_run.run_count = 4
        ctx.run.flow_run_run_count = 2
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in rerun_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.run.run_count == 0
        assert ctx.proposed_state.name == "Retrying"
        assert (
            ctx.run.flow_run_run_count == 4
        ), "Orchestration should update the flow run run count tracker"

    async def test_cleans_up_after_invalid_transition(
        self,
        session,
        initialize_orchestration,
        fizzling_rule,
    ):
        rerun_policy = [
            HandleTaskTerminalStateTransitions,
            UpdateFlowRunTrackerOnTasks,
            fizzling_rule,
        ]
        initial_state_type = states.StateType.FAILED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            flow_retries=10,
        )
        flow_run = await ctx.flow_run()
        flow_run.run_count = 4
        ctx.run.flow_run_run_count = 2
        ctx.run.run_count = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in rerun_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.run.run_count == 2
        assert ctx.proposed_state.name == "Retrying"
        assert ctx.run.flow_run_run_count == 2


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

    async def test_task_retry_uses_configured_delay(
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
        run_settings.retry_delay = 10

        async with contextlib.AsyncExitStack() as stack:
            orchestration_start = pendulum.now("UTC")
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        scheduled_time = ctx.validated_state.state_details.scheduled_time
        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED
        assert math.isclose(
            (scheduled_time - orchestration_start).in_seconds(), 10, rel_tol=0.1
        )

    @pytest.mark.parametrize("retry", [1, 2, 3, 4, 5])
    async def test_retry_uses_configured_delays(
        self, session, initialize_orchestration, retry
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
        orm_run.run_count = retry
        run_settings.retries = 5

        configured_retry_delays = [2, 3, 5, 7, 11]
        run_settings.retry_delay = configured_retry_delays

        async with contextlib.AsyncExitStack() as stack:
            orchestration_start = pendulum.now("UTC")
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        scheduled_time = ctx.validated_state.state_details.scheduled_time
        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED
        assert math.isclose(
            (scheduled_time - orchestration_start).in_seconds(),
            configured_retry_delays[retry - 1],
            rel_tol=0.1,
        )

    async def test_retry_uses_falls_back_to_last_delay(
        self, session, initialize_orchestration
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
        orm_run.run_count = 6
        run_settings.retries = 6

        configured_retry_delays = [2, 3, 5, 7]
        run_settings.retry_delay = configured_retry_delays

        async with contextlib.AsyncExitStack() as stack:
            orchestration_start = pendulum.now("UTC")
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        scheduled_time = ctx.validated_state.state_details.scheduled_time
        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED
        assert math.isclose(
            (scheduled_time - orchestration_start).in_seconds(),
            configured_retry_delays[-1],
            rel_tol=0.1,
        )

    async def test_retries_can_jitter_sleeps(
        self, session, initialize_orchestration, monkeypatch
    ):
        def randomizer(average_interval, clamping_factor=0.3):
            # is not really a randomizer
            return average_interval * (1 + clamping_factor)

        monkeypatch.setattr(
            "prefect.server.orchestration.core_policy.clamped_poisson_interval",
            randomizer,
        )

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

        run_settings.retry_delay = 10
        run_settings.retry_jitter_factor = 9

        async with contextlib.AsyncExitStack() as stack:
            orchestration_start = pendulum.now("UTC")
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        scheduled_time = ctx.validated_state.state_details.scheduled_time
        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.SCHEDULED
        assert math.isclose(
            (scheduled_time - orchestration_start).in_seconds(),
            100,
            rel_tol=0.1,
        )

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
    all_transitions = set(product(ALL_ORCHESTRATION_STATES, CANONICAL_STATES))
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

        if run_type == "task":
            protection_rule = HandleTaskTerminalStateTransitions
        elif run_type == "flow":
            protection_rule = HandleFlowTerminalStateTransitions

        state_protection = protection_rule(ctx, *intended_transition)

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

        if run_type == "task":
            protection_rule = HandleTaskTerminalStateTransitions
        elif run_type == "flow":
            protection_rule = HandleFlowTerminalStateTransitions

        state_protection = protection_rule(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestPreventingRedundantTransitionsRule:
    active_states = (
        states.StateType.CANCELLING,
        states.StateType.RUNNING,
        states.StateType.PENDING,
        states.StateType.SCHEDULED,
        None,
    )
    all_transitions = set(product(ALL_ORCHESTRATION_STATES, ALL_ORCHESTRATION_STATES))
    redundant_transitions = set(combinations_with_replacement(active_states, 2))

    # Cast to sorted lists for deterministic ordering.
    # Sort as strings to handle `None`.
    active_transitions = list(
        sorted(all_transitions - redundant_transitions, key=lambda item: str(item))
    )
    redundant_transitions = list(
        sorted(redundant_transitions, key=lambda item: str(item))
    )

    @pytest.mark.parametrize(
        "intended_transition", redundant_transitions, ids=transition_names
    )
    async def test_redundant_transitions_are_aborted(
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

        state_protection = PreventRedundantTransitions(ctx, *intended_transition)

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

        state_protection = PreventRedundantTransitions(ctx, *intended_transition)

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

    async def test_concurrency_limit_cancelling_transition(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        await self.create_concurrency_limit(session, "some tag", 1)
        concurrency_policy = [SecureTaskConcurrencySlots, ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        cancelling_transition = (states.StateType.RUNNING, states.StateType.CANCELLING)
        cancelled_transition = (states.StateType.CANCELLING, states.StateType.CANCELLED)

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

        task1_cancelling_ctx = await initialize_orchestration(
            session,
            "task",
            *cancelling_transition,
            run_override=task1_running_ctx.run,
            run_tags=["some tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_cancelling_ctx = await stack.enter_async_context(
                    rule(task1_cancelling_ctx, *cancelling_transition)
                )
            await task1_cancelling_ctx.validate_proposed_state()

        # the first task run will transition into a cancelling state, but
        # maintain a hold on the concurrency slot
        assert task1_cancelling_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "some tag")) == 1

        task1_cancelled_ctx = await initialize_orchestration(
            session,
            "task",
            *cancelled_transition,
            run_override=task1_running_ctx.run,
            run_tags=["some tag"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                task1_cancelled_ctx = await stack.enter_async_context(
                    rule(task1_cancelled_ctx, *cancelled_transition)
                )
            await task1_cancelled_ctx.validate_proposed_state()

        # the first task run will transition into a cancelled state, yielding a
        # concurrency slot
        assert task1_cancelled_ctx.response_status == SetStateStatus.ACCEPT
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

        # instead of a WAIT response, Prefect should direct the client to ABORT
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

    async def test_returning_concurrency_slots_when_transitioning_out_of_running_even_on_fizzle(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        """Make sure that we return the concurrency slot when even on a fizzle as long as we transition
        out of running, with ReleaseTaskConcurrencySlots listed first in priority.
        """

        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                mutated_state = proposed_state.copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {
                            initial_state.type,
                            proposed_state.type,
                            states.StateType.RUNNING,
                            states.StateType.CANCELLING,
                        }
                    )
                )
                await self.reject_transition(
                    mutated_state, reason="gotta fizzle some rules, for fun"
                )

            async def after_transition(self, initial_state, validated_state, context):
                pass

            async def cleanup(self, initial_state, validated_state, context):
                pass

        accept_concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        reject_concurrency_policy = [
            ReleaseTaskConcurrencySlots,
            SecureTaskConcurrencySlots,
            StateMutatingRule,
        ]

        await self.create_concurrency_limit(session, "small", 1)

        # Fill the concurrency slot by transitioning into a running state
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["small"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in accept_concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "small")) == 1

        # Make sure that the concurrency slot is released even though the transition was
        # rejected, because the task was still moved out of a RUNNING state
        pending_transition = (states.StateType.RUNNING, states.StateType.PENDING)

        task1_pending_ctx = await initialize_orchestration(
            session,
            "task",
            *pending_transition,
            run_override=task1_running_ctx.run,
            run_tags=["small"],
        )
        async with contextlib.AsyncExitStack() as stack:
            for rule in reject_concurrency_policy:
                task1_pending_ctx = await stack.enter_async_context(
                    rule(task1_pending_ctx, *pending_transition)
                )
            await task1_pending_ctx.validate_proposed_state()

        assert task1_pending_ctx.response_status == SetStateStatus.REJECT
        assert task1_pending_ctx.validated_state.type != states.StateType.RUNNING
        assert (await self.count_concurrency_slots(session, "small")) == 0

    async def test_returning_concurrency_slots_when_transitioning_out_of_running_even_on_invalidation(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        """Make sure that we return the concurrency slot when even on a fizzle as long as we transition
        out of running, with ReleaseTaskConcurrencySlots listed last in priority.
        """

        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                mutated_state = proposed_state.copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {
                            initial_state.type,
                            proposed_state.type,
                            states.StateType.CANCELLING,
                        }
                    )
                )
                await self.reject_transition(
                    mutated_state, reason="gotta fizzle some rules, for fun"
                )

            async def after_transition(self, initial_state, validated_state, context):
                pass

            async def cleanup(self, initial_state, validated_state, context):
                pass

        accept_concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        reject_concurrency_policy = [
            StateMutatingRule,
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        await self.create_concurrency_limit(session, "small", 1)

        # Fill the concurrency slot by transitioning into a running state
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["small"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in accept_concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "small")) == 1

        # Make sure that the concurrency slot is released even though the transition was
        # rejected, because the task was still moved out of a RUNNING state
        pending_transition = (states.StateType.RUNNING, states.StateType.PENDING)

        task1_pending_ctx = await initialize_orchestration(
            session,
            "task",
            *pending_transition,
            run_override=task1_running_ctx.run,
            run_tags=["small"],
        )
        async with contextlib.AsyncExitStack() as stack:
            for rule in reject_concurrency_policy:
                task1_pending_ctx = await stack.enter_async_context(
                    rule(task1_pending_ctx, *pending_transition)
                )
            await task1_pending_ctx.validate_proposed_state()

        assert task1_pending_ctx.response_status == SetStateStatus.REJECT
        assert task1_pending_ctx.validated_state.type != states.StateType.RUNNING
        assert (await self.count_concurrency_slots(session, "small")) == 0

    async def test_releasing_concurrency_slots_does_not_happen_if_nullified_with_release_first(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        """Make sure that concurrency slots are not released if the transition is nullified,
        with ReleaseTaskConcurrencySlots listed first in priority
        """

        class NullifiedTransition(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                await self.abort_transition(reason="For testing purposes")

            async def after_transition(self, initial_state, validated_state, context):
                pass

            async def cleanup(self, initial_state, validated_state, context):
                pass

        accept_concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        abort_concurrency_policy = [
            ReleaseTaskConcurrencySlots,
            SecureTaskConcurrencySlots,
            NullifiedTransition,
        ]

        await self.create_concurrency_limit(session, "small", 1)

        # Fill the concurrency slot by transitioning into a running state
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["small"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in accept_concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "small")) == 1

        # Make sure that the concurrency slot is not released because the transition
        # was aborted
        pending_transition = (states.StateType.RUNNING, states.StateType.PENDING)

        task1_pending_ctx = await initialize_orchestration(
            session,
            "task",
            *pending_transition,
            run_override=task1_running_ctx.run,
            run_tags=["small"],
        )

        async with contextlib.AsyncExitStack() as stack:  # Here
            for rule in abort_concurrency_policy:
                task1_pending_ctx = await stack.enter_async_context(
                    rule(task1_pending_ctx, *pending_transition)
                )
            await task1_pending_ctx.validate_proposed_state()

        assert task1_pending_ctx.response_status == SetStateStatus.ABORT
        assert (await self.count_concurrency_slots(session, "small")) == 1

    async def test_releasing_concurrency_slots_does_not_happen_if_nullified_with_release_last(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        """Make sure that concurrency slots are not released if the transition is nullified,
        with ReleaseTaskConcurrencySlots listed last in priority
        """

        class NullifiedTransition(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                await self.abort_transition(reason="For testing purposes")

            async def after_transition(self, initial_state, validated_state, context):
                pass

            async def cleanup(self, initial_state, validated_state, context):
                pass

        accept_concurrency_policy = [
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        abort_concurrency_policy = [
            NullifiedTransition,
            SecureTaskConcurrencySlots,
            ReleaseTaskConcurrencySlots,
        ]

        await self.create_concurrency_limit(session, "small", 1)

        # Fill the concurrency slot by transitioning into a running state
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["small"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in accept_concurrency_policy:
                task1_running_ctx = await stack.enter_async_context(
                    rule(ctx, *running_transition)
                )
            await task1_running_ctx.validate_proposed_state()

        assert task1_running_ctx.response_status == SetStateStatus.ACCEPT
        assert (await self.count_concurrency_slots(session, "small")) == 1

        # Make sure that the concurrency slot is not released because the transition
        # was aborted
        pending_transition = (states.StateType.RUNNING, states.StateType.PENDING)

        task1_pending_ctx = await initialize_orchestration(
            session,
            "task",
            *pending_transition,
            run_override=task1_running_ctx.run,
            run_tags=["small"],
        )

        async with contextlib.AsyncExitStack() as stack:  # Here
            for rule in abort_concurrency_policy:
                task1_pending_ctx = await stack.enter_async_context(
                    rule(task1_pending_ctx, *pending_transition)
                )
            await task1_pending_ctx.validate_proposed_state()

        assert task1_pending_ctx.response_status == SetStateStatus.ABORT
        assert (await self.count_concurrency_slots(session, "small")) == 1


class TestPausingFlows:
    async def test_can_not_nonblocking_pause_subflows(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.state_details = states.StateDetails(pause_reschedule=True)
        ctx.run.parent_task_run_id == uuid4()

        state_protection = HandlePausingFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ABORT

    async def test_can_not_nonblocking_pause_flows_with_deployments_with_reschedule_flag(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.state_details = states.StateDetails(pause_reschedule=True)

        state_protection = HandlePausingFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ABORT

    async def test_can_nonblocking_pause_flows_with_deployments_with_reschedule_flag(
        self,
        session,
        initialize_orchestration,
        deployment,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.state_details = states.StateDetails(pause_reschedule=True)
        ctx.run.deployment_id = deployment.id

        state_protection = HandlePausingFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

    async def test_updates_pause_key_tracker(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state = states.Paused(pause_key="hello", timeout_seconds=1000)

        async with HandlePausingFlows(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert "hello" in ctx.run.empirical_policy.pause_keys

    async def test_defaults_pause_key_to_random_uuid(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state = states.Paused(pause_key="hello", timeout_seconds=1000)

        assert len(ctx.run.empirical_policy.pause_keys) == 0

        async with HandlePausingFlows(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert len(ctx.run.empirical_policy.pause_keys) == 1

    async def test_does_not_permit_repeat_pauses(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state = states.Paused(pause_key="hello", timeout_seconds=1000)

        async with HandlePausingFlows(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

        ctx2 = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
            run_override=ctx.run,
        )
        ctx2.proposed_state = states.Paused(pause_key="hello", timeout_seconds=1000)

        async with HandlePausingFlows(ctx2, *intended_transition) as ctx2:
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.REJECT
        assert ctx2.validated_state.type == states.StateType.RUNNING

    @pytest.mark.parametrize("initial_state_type", ALL_ORCHESTRATION_STATES)
    async def test_can_only_pause_running_flows(
        self,
        session,
        initial_state_type,
        initialize_orchestration,
        deployment,
    ):
        proposed_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.deployment_id = deployment.id

        state_protection = HandlePausingFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        if ctx.initial_state is None:
            assert ctx.response_status == SetStateStatus.ABORT
        elif ctx.initial_state.is_running():
            assert ctx.response_status == SetStateStatus.ACCEPT
        else:
            assert ctx.response_status == SetStateStatus.REJECT
            assert ctx.validated_state_type == initial_state_type


class TestResumingFlows:
    async def test_cannot_leave_nonblocking_pausing_state_without_a_deployment(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        five_minutes_from_now = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        ctx.initial_state.state_details = states.StateDetails(
            pause_timeout=five_minutes_from_now, pause_reschedule=True
        )

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.PAUSED

    async def test_can_leave_blocking_pausing_state_without_a_deployment(
        self,
        session,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        five_minutes_from_now = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        ctx.initial_state.state_details = states.StateDetails(
            pause_timeout=five_minutes_from_now
        )

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

    @pytest.mark.parametrize("proposed_state_type", list(states.StateType))
    async def test_transitions_out_of_pausing_states_are_restricted(
        self,
        session,
        proposed_state_type,
        deployment,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.deployment_id = deployment.id

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        permitted_resuming_states = [
            states.StateType.RUNNING,
            states.StateType.COMPLETED,
            states.StateType.SCHEDULED,
            states.StateType.FAILED,
            states.StateType.CRASHED,
            states.StateType.CANCELLED,
        ]

        if proposed_state_type in permitted_resuming_states:
            assert ctx.response_status == SetStateStatus.ACCEPT
        else:
            assert ctx.response_status == SetStateStatus.REJECT
            assert ctx.validated_state_type == initial_state_type

    async def test_cannot_leave_pausing_state_if_pause_has_timed_out(
        self,
        session,
        deployment,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.deployment_id = deployment.id
        five_minutes_ago = pendulum.now("UTC") - pendulum.Duration(minutes=5)
        ctx.initial_state.state_details = states.StateDetails(
            pause_timeout=five_minutes_ago
        )

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state.type == states.StateType.FAILED

    async def test_allows_leaving_pausing_state(
        self,
        session,
        deployment,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.deployment_id = deployment.id
        the_future = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        ctx.initial_state.state_details = states.StateDetails(pause_timeout=the_future)

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

    async def test_marks_flow_run_as_resuming_upon_leaving_paused_state(
        self,
        session,
        deployment,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PAUSED
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.deployment_id = deployment.id
        the_future = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        ctx.initial_state.state_details = states.StateDetails(pause_timeout=the_future)

        state_protection = HandleResumingPausedFlows(ctx, *intended_transition)

        async with state_protection as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.run.empirical_policy.resuming


class TestPreventRunningTasksFromStoppedFlows:
    async def test_allows_task_runs_to_run(self, session, initialize_orchestration):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_flow_run_state_type=states.StateType.RUNNING,
        )

        run_preventer = PreventRunningTasksFromStoppedFlows(ctx, *intended_transition)

        async with run_preventer as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.validated_state.is_running()

    @pytest.mark.parametrize(
        "initial_flow_run_state_type",
        sorted(list(set(states.StateType) - {states.StateType.RUNNING})),
    )
    async def test_prevents_tasks_From_running(
        self, session, initial_flow_run_state_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "task",
            *intended_transition,
            initial_flow_run_state_type=initial_flow_run_state_type,
        )

        run_preventer = PreventRunningTasksFromStoppedFlows(ctx, *intended_transition)

        async with run_preventer as ctx:
            await ctx.validate_proposed_state()

        if initial_flow_run_state_type == states.StateType.PAUSED:
            assert ctx.response_status == SetStateStatus.REJECT
            assert ctx.validated_state.is_paused()
        else:
            assert ctx.response_status == SetStateStatus.ABORT
            assert ctx.validated_state.is_pending()


class TestHandleCancellingStateTransitions:
    @pytest.mark.parametrize(
        "proposed_state_type",
        sorted(
            list(set(ALL_ORCHESTRATION_STATES) - {states.StateType.CANCELLED, None})
        ),
    )
    async def test_rejects_cancelling_to_anything_but_cancelled(
        self,
        session,
        initialize_orchestration,
        proposed_state_type,
    ):
        initial_state_type = states.StateType.CANCELLING
        intended_transition = (initial_state_type, proposed_state_type)

        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )

        async with HandleCancellingStateTransitions(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.CANCELLING

    @pytest.mark.parametrize(
        "proposed_state_type",
        sorted(
            list(set(ALL_ORCHESTRATION_STATES) - {states.StateType.CANCELLED, None})
        ),
    )
    async def test_rejects_cancelled_cancelling_to_anything_but_cancelled(
        self,
        session,
        initialize_orchestration,
        proposed_state_type,
    ):
        initial_state_type = states.StateType.CANCELLING
        intended_transition = (initial_state_type, proposed_state_type)

        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )

        async with HandleCancellingStateTransitions(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state_type == states.StateType.CANCELLING
