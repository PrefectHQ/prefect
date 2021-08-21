import contextlib
import pytest
import pendulum
from unittest.mock import MagicMock
from uuid import UUID

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

    @pytest.mark.parametrize("mutating_state", ["initial", "proposed"])
    async def test_fizzled_rules_fire_before_hooks_then_cleanup(
        self, session, task_run, mutating_state
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
            if mutating_state == "initial":
                ctx.initial_state = mutated_state
            elif mutating_state == "proposed":
                ctx.proposed_state = mutated_state
        assert await minimal_rule.invalid() is False
        assert await minimal_rule.fizzled() is True

        # fizzled fire on entry, but have an opportunity to clean up side effects
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 0
        assert cleanup_step.call_count == 1

    async def test_rules_that_mutate_state_do_not_fizzle_themselves(
        self, session, task_run
    ):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class StateMutatingRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.copy()
                mutated_state.type = initial_state_type
                before_transition_hook()
                return mutated_state

            async def after_transition(self, initial_state, proposed_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
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

        mutating_rule = StateMutatingRule(ctx, *intended_transition)
        async with mutating_rule as _:
            pass
        assert await mutating_rule.invalid() is False
        assert await mutating_rule.fizzled() is False

        # despite the mutation, this rule is valid so before and after hooks will fire
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 1
        assert cleanup_step.call_count == 0

    async def test_nested_valid_rules_fire_hooks(self, session, task_run):
        first_before_hook = MagicMock()
        second_before_hook = MagicMock()
        first_after_hook = MagicMock()
        second_after_hook = MagicMock()
        cleanup_step = MagicMock()

        class FirstMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                first_before_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                first_after_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        class SecondMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                second_before_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                second_after_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_step()

        # both rules are valid
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

        async with contextlib.AsyncExitStack() as stack:
            first_rule = FirstMinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(first_rule)

            # after entering the first context, only one before hook as fired
            assert first_before_hook.call_count == 1
            assert first_after_hook.call_count == 0
            assert second_before_hook.call_count == 0
            assert second_after_hook.call_count == 0
            assert cleanup_step.call_count == 0

            second_rule = SecondMinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(second_rule)

            # the second before hook fires after entering the second context
            # note that no after hooks have fired yet
            assert first_before_hook.call_count == 1
            assert first_after_hook.call_count == 0
            assert second_before_hook.call_count == 1
            assert second_after_hook.call_count == 0
            assert cleanup_step.call_count == 0

        assert await first_rule.invalid() is False
        assert await second_rule.invalid() is False
        assert await first_rule.fizzled() is False
        assert await second_rule.fizzled() is False

        # both the first and second after hooks fired after exiting the contexts
        # none of the rules fizzled, so the cleanup step is never called
        assert first_before_hook.call_count == 1
        assert first_after_hook.call_count == 1
        assert second_before_hook.call_count == 1
        assert second_after_hook.call_count == 1
        assert cleanup_step.call_count == 0

    async def test_complex_policy_invalidates_unnecessary_rules(
        self, session, task_run
    ):
        first_before_hook = MagicMock()
        mutator_before_hook = MagicMock()
        invalid_before_hook = MagicMock()
        first_after_hook = MagicMock()
        mutator_after_hook = MagicMock()
        invalid_after_hook = MagicMock()
        cleanup_after_fizzling = MagicMock()
        mutator_cleanup = MagicMock()
        invalid_cleanup = MagicMock()

        class FirstMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                first_before_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                first_after_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                cleanup_after_fizzling()

        class StateMutatingRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.copy()
                mutated_state.type = initial_state_type
                mutator_before_hook()
                return mutated_state

            async def after_transition(self, initial_state, proposed_state, context):
                mutator_after_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                mutator_cleanup()

        class InvalidatedRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                invalid_before_hook()
                return proposed_state

            async def after_transition(self, initial_state, proposed_state, context):
                invalid_after_hook()

            async def cleanup(self, initial_state, proposed_state, context):
                invalid_cleanup()

        # all rules start valid
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

        async with contextlib.AsyncExitStack() as stack:
            first_rule = FirstMinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(first_rule)

            # after entering the first context, only one before hook as fired
            assert first_before_hook.call_count == 1
            assert mutator_before_hook.call_count == 0
            assert invalid_before_hook.call_count == 0

            mutator_rule = StateMutatingRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(mutator_rule)

            # the mutator fires after entering the second context and changes the proposed state
            # this mutation will invalidate any subsequent rules and fizzle previous ones
            assert first_before_hook.call_count == 1
            assert mutator_before_hook.call_count == 1
            assert invalid_before_hook.call_count == 0

            invalidated_rule = InvalidatedRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(invalidated_rule)

            # invalid rule hooks don't fire, even after entering their context
            assert first_before_hook.call_count == 1
            assert mutator_before_hook.call_count == 1
            assert invalid_before_hook.call_count == 0

        # after closing all contexts, the first rule fizzles and cleans up
        assert await first_rule.invalid() is False
        assert await first_rule.fizzled() is True
        assert first_before_hook.call_count == 1
        assert first_after_hook.call_count == 0
        assert cleanup_after_fizzling.call_count == 1

        # the rule responsible for mutation remains valid
        assert await mutator_rule.invalid() is False
        assert await mutator_rule.fizzled() is False
        assert mutator_before_hook.call_count == 1
        assert mutator_after_hook.call_count == 1
        assert mutator_cleanup.call_count == 0

        # the invalid rule fires no hooks at all
        assert await invalidated_rule.invalid() is True
        assert await invalidated_rule.fizzled() is False
        assert invalid_before_hook.call_count == 0
        assert invalid_after_hook.call_count == 0
        assert invalid_cleanup.call_count == 0
