"""
Tests for FlowRunPolicy retry counters (in_process_retries and reschedule_retries).
"""

import contextlib
from uuid import uuid4

import pytest

from prefect.server.orchestration.core_policy import (
    HandleFlowTerminalStateTransitions,
    RetryFailedFlows,
)
from prefect.server.schemas.responses import SetStateStatus
from prefect.server.schemas.states import StateType


class TestInProcessRetryCounter:
    """Tests for in_process_retries counter tracking automatic flow retries."""

    async def test_in_process_retries_increments_on_automatic_retry(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify in_process_retries increments when an automatic retry is triggered."""
        retry_policy = [RetryFailedFlows]
        initial_state_type = StateType.RUNNING
        proposed_state_type = StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.run_count = 1
        ctx.run_settings.retries = 3
        ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
        ctx.run.empirical_policy.in_process_retries = 0

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.run.empirical_policy.retry_type == "in_process"
        assert ctx.run.empirical_policy.in_process_retries == 1

    async def test_in_process_retries_multiple_retries(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify in_process_retries increments across multiple automatic retries."""
        retry_policy = [RetryFailedFlows]
        initial_state_type = StateType.RUNNING
        proposed_state_type = StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)

        for retry_num in range(1, 4):
            ctx = await initialize_orchestration(
                session,
                "flow",
                *intended_transition,
            )
            ctx.run.run_count = retry_num
            ctx.run_settings.retries = 5
            ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
            ctx.run.empirical_policy.in_process_retries = retry_num - 1

            async with contextlib.AsyncExitStack() as stack:
                for rule in retry_policy:
                    ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
                await ctx.validate_proposed_state()

            assert ctx.run.empirical_policy.retry_type == "in_process"
            assert ctx.run.empirical_policy.in_process_retries == retry_num

    async def test_in_process_retries_does_not_increment_on_exhausted_retries(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify in_process_retries does NOT increment when retries are exhausted."""
        retry_policy = [RetryFailedFlows]
        initial_state_type = StateType.RUNNING
        proposed_state_type = StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.run.run_count = 2 
        ctx.run_settings.retries = 1
        ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
        ctx.run.empirical_policy.in_process_retries = 2

        async with contextlib.AsyncExitStack() as stack:
            for rule in retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))
            await ctx.validate_proposed_state()

        assert ctx.run.empirical_policy.retry_type is None
        assert ctx.run.empirical_policy.in_process_retries == 2


class TestRescheduleRetryCounter:
    """Tests for reschedule_retries counter tracking manual flow reschedules."""

    async def test_reschedule_retries_increments_on_manual_reschedule(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify reschedule_retries increments when a manual reschedule is triggered."""
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = StateType.FAILED
        proposed_state_type = StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.deployment_id = uuid4()
        ctx.run.run_count = 2
        ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
        ctx.run.empirical_policy.reschedule_retries = 0

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.run.empirical_policy.retry_type == "reschedule"
        assert ctx.run.empirical_policy.reschedule_retries == 1

    async def test_reschedule_retries_does_not_increment_for_non_scheduled_states(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify reschedule_retries does NOT increment when transitioning to non-scheduled states."""
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = StateType.FAILED
        proposed_state_type = StateType.FAILED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.deployment_id = uuid4()
        ctx.run.run_count = 2
        ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
        ctx.run.empirical_policy.reschedule_retries = 5

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.run.empirical_policy.retry_type is None
        assert ctx.run.empirical_policy.reschedule_retries == 5


class TestRetryCountersIndependence:
    """Tests to verify in_process_retries and reschedule_retries are independent."""

    async def test_in_process_and_reschedule_counters_are_independent(
        self,
        session,
        initialize_orchestration,
    ):
        """Verify that in_process_retries and reschedule_retries don't interfere with each other."""
        manual_retry_policy = [HandleFlowTerminalStateTransitions]
        initial_state_type = StateType.FAILED
        proposed_state_type = StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)

        ctx = await initialize_orchestration(
            session,
            "flow",
            *intended_transition,
        )
        ctx.proposed_state.name = "AwaitingRetry"
        ctx.run.deployment_id = uuid4()
        ctx.run.run_count = 2

        ctx.run.empirical_policy = ctx.run.empirical_policy.model_copy()
        ctx.run.empirical_policy.in_process_retries = 5
        ctx.run.empirical_policy.reschedule_retries = 3

        async with contextlib.AsyncExitStack() as stack:
            for rule in manual_retry_policy:
                ctx = await stack.enter_async_context(rule(ctx, *intended_transition))

        assert ctx.run.empirical_policy.in_process_retries == 5
        assert ctx.run.empirical_policy.reschedule_retries == 4
        assert ctx.run.empirical_policy.retry_type == "reschedule"
