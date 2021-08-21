from uuid import UUID
import pendulum
from unittest.mock import MagicMock
from prefect.orion.orchestration.rules import (
    BaseOrchestrationRule,
    OrchestrationContext,
)
from prefect.orion import schemas, models
from prefect.orion.schemas import states


async def create_task_run_state(
    session, task_run, state_type: schemas.actions.StateCreate, state_details=dict()
):
    new_state = schemas.actions.StateCreate(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    return await models.task_run_states.create_task_run_state(
        session=session,
        task_run_id=task_run.id,
        state=new_state,
    )


class TestBaseOrchestrationRule:
    async def test_valid_rules_fire_before_and_after_transitions(
        self, session, task_run
    ):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        # rules are valid if the initial and proposed state always match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = (
            await create_task_run_state(session, task_run, initial_state_type)
        ).as_state()
        proposed_state = initial_state.copy()
        proposed_state.type = proposed_state_type

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=MagicMock(),
            run=MagicMock(),
            task_run_id=UUID(int=42),
        )

        minimal_rule = MinimalRule(ctx, *intended_transition)
        async with minimal_rule as _:
            pass
        assert await minimal_rule.invalid() is False
        assert await minimal_rule.fizzled() is False
        # before and after hooks fire for valid rules
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 1
        assert cleanup_step.call_count == 0

    async def test_invalid_rules_are_noops(self, session, task_run):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        # a rule is invalid if it is applied on initial and proposed states that do not match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (states.StateType.SCHEDULED, states.StateType.COMPLETED)
        initial_state = (
            await create_task_run_state(session, task_run, initial_state_type)
        ).as_state()
        proposed_state = initial_state.copy()
        proposed_state.type = proposed_state_type

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=MagicMock(),
            run=MagicMock(),
            task_run_id=UUID(int=42),
        )

        minimal_rule = MinimalRule(ctx, *intended_transition)
        async with minimal_rule as _:
            pass
        assert await minimal_rule.invalid() is True
        assert await minimal_rule.fizzled() is False
        # none of the hooks fire for invalid rules
        assert before_transition_hook.call_count == 0
        assert after_transition_hook.call_count == 0
        assert cleanup_step.call_count == 0

    async def test_fizzled_rules_fire_before_hooks_then_cleanup(
        self, session, task_run
    ):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        # if either the initial or proposed states change after the rule starts firing, it will fizzle
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = (
            await create_task_run_state(session, task_run, initial_state_type)
        ).as_state()
        proposed_state = initial_state.copy()
        proposed_state.type = proposed_state_type

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=MagicMock(),
            run=MagicMock(),
            task_run_id=UUID(int=42),
        )

        minimal_rule = MinimalRule(ctx, *intended_transition)
        async with minimal_rule as _:
            # mutating the proposed state inside the context will fizzle the rule
            mutated_state = proposed_state.copy()
            mutated_state.type = states.StateType.COMPLETED
            ctx.proposed_state = mutated_state
        assert await minimal_rule.invalid() is False
        assert await minimal_rule.fizzled() is True
        # fizzled fire on entry, but have an opportunity to clean up side effects
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 0
        assert cleanup_step.call_count == 1
