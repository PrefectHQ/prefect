import math
import pendulum
import pytest

from prefect.orion.orchestration.rules import ALL_ORCHESTRATION_STATES
from prefect.orion.orchestration.global_policy import (
    UpdateRunDetails,
)
from prefect.orion.schemas import states


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestUpdateRunDetailsRule:
    @pytest.mark.parametrize("proposed_state_type", ALL_ORCHESTRATION_STATES)
    async def test_rule_updates_run_state(
        self,
        session,
        run_type,
        initialize_orchestration,
        proposed_state_type
    ):
        initial_state_type = None
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        run = await ctx.orm_run()
        assert run.state_type == proposed_state_type

    async def test_rule_sets_scheduled_time(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = None
        proposed_state_type = states.StateType.SCHEDULED
        intended_transition = (initial_state_type, proposed_state_type)
        scheduled_time = pendulum.now().add(seconds=42)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
            proposed_details={"scheduled_time": scheduled_time}
        )

        run = await ctx.orm_run()
        assert run.start_time is None

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert run.next_scheduled_start_time == scheduled_time
        assert run.expected_start_time == scheduled_time
        assert run.start_time is None

    async def test_rule_sets_expected_start_time(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.SCHEDULED
        proposed_state_type = states.StateType.PENDING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        run = await ctx.orm_run()
        assert run.start_time is None

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert run.expected_start_time is not None
        assert run.start_time is None

    async def test_rule_sets_start_time_when_starting_to_run(
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

        run = await ctx.orm_run()
        assert run.start_time is None

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert run.start_time is not None

    async def test_rule_updates_run_count_when_starting_to_run(
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

        run = await ctx.orm_run()
        assert run.run_count == 0

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert run.run_count == 1

    async def test_rule_increments_run_count(
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

        run = await ctx.orm_run()
        run.run_count = 41

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert run.run_count == 42

    async def test_rule_updates_run_time_after_running(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.RUNNING
        proposed_state_type = states.StateType.COMPLETED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        run = await ctx.orm_run()
        run.start_time = pendulum.now().subtract(seconds=42)
        ctx.initial_state.timestamp = pendulum.now().subtract(seconds=42)
        assert run.total_run_time_seconds == 0

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert math.ceil(run.total_run_time_seconds) == 42

    async def test_rule_doesnt_update_run_time_when_not_running(
        self,
        session,
        run_type,
        initialize_orchestration,
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.COMPLETED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        run = await ctx.orm_run()
        run.start_time = pendulum.now().subtract(seconds=42)
        ctx.initial_state.timestamp = pendulum.now().subtract(seconds=42)
        assert run.total_run_time_seconds == 0

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert math.ceil(run.total_run_time_seconds) == 0

    @pytest.mark.parametrize("initial_state_type", set(states.StateType))
    async def test_rule_always_updates_total_time(
        self,
        session,
        run_type,
        initialize_orchestration,
        initial_state_type
    ):
        proposed_state_type = states.StateType.COMPLETED
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(
            session,
            run_type,
            *intended_transition,
        )

        run = await ctx.orm_run()
        run.start_time = pendulum.now().subtract(seconds=42)
        ctx.initial_state.timestamp = pendulum.now().subtract(seconds=42)
        assert run.total_run_time_seconds == 0

        async with UpdateRunDetails(ctx, *intended_transition) as ctx:
            await ctx.validate_proposed_state()

        assert math.ceil(run.total_time_seconds) == 42

