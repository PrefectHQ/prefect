import contextlib
import random
from itertools import product
from unittest.mock import MagicMock

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.orchestration.rules import (
    BaseOrchestrationRule,
    BaseUniversalRule,
    OrchestrationContext,
)
from prefect.orion.schemas import states


async def create_task_run_state(
    session, task_run, state_type: schemas.actions.StateCreate, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details
    new_state = schemas.actions.StateCreate(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    return (
        await models.task_run_states.orchestrate_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=new_state,
        )
    ).state


class TestBaseOrchestrationRule:
    async def test_orchestration_rules_are_context_managers(self, session, task_run):

        side_effect = 0

        class IllustrativeRule(BaseOrchestrationRule):
            # we implement rules by inheriting from `BaseOrchestrationRule`
            # in order to do so, we need to define three methods:

            # a before-transition hook that fires upon entering the rule
            # this method returns a proposed state, and is the only opportunity for a rule
            # to modify the state transition
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effect
                side_effect += 1

            # an after-transition hook that fires after a state is validated and committed to the DB
            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effect
                side_effect += 1

            # the cleanup step allows a rule to revert side-effects caused
            # by the before-transition hook in case the transition does not complete
            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effect
                side_effect -= 1

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        rule_as_context_manager = IllustrativeRule(ctx, *intended_transition)
        context_call = MagicMock()

        # rules govern logic by being used as a context manager
        async with rule_as_context_manager as ctx:
            context_call()

        assert context_call.call_count == 1

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

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # rules are valid if the initial and proposed state always match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        minimal_rule = MinimalRule(ctx, *intended_transition)
        async with minimal_rule as ctx:
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

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # a rule is invalid if it is applied on initial and proposed states that do not match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (states.StateType.SCHEDULED, states.StateType.COMPLETED)
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        # each rule receives a context as an argument and yields it back after
        # entering its context--this way we can thread a common context
        # through a series of nested rules
        minimal_rule = MinimalRule(ctx, *intended_transition)
        async with minimal_rule as ctx:
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
        side_effect = 0
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class FizzlingRule(BaseOrchestrationRule):
            # the before transition hook causes a side-effect
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effect
                side_effect += 1
                before_transition_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effect
                side_effect += 1
                after_transition_hook()

            # the cleanup step allows a rule to revert side-effects caused
            # by the before-transition hook in the event of a fizzle
            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effect
                side_effect -= 1
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        # if either the initial or proposed states change after the rule starts firing, it will fizzle
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        fizzling_rule = FizzlingRule(ctx, *intended_transition)
        async with fizzling_rule as ctx:

            # within the context, only the before-hook has fired and we can observe the side-effect
            assert side_effect == 1

            # mutating the proposed state inside the context will fizzle the rule
            mutated_state = proposed_state.copy()
            mutated_state.type = random.choice(
                list(set(states.StateType) - {*intended_transition})
            )
            if mutating_state == "initial":
                ctx.initial_state = mutated_state
            elif mutating_state == "proposed":
                ctx.proposed_state = mutated_state

        # outside of the context the rule will have fizzled and the side effect was cleaned up
        assert side_effect == 0
        assert await fizzling_rule.invalid() is False
        assert await fizzling_rule.fizzled() is True
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
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {initial_state.type, proposed_state.type}
                    )
                )
                before_transition_hook()
                await self.reject_transition(
                    mutated_state, reason="for testing, of course"
                )

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        mutating_rule = StateMutatingRule(ctx, *intended_transition)
        async with mutating_rule as ctx:
            pass
        assert await mutating_rule.invalid() is False
        assert await mutating_rule.fizzled() is False

        # despite the mutation, this rule is valid so before and after hooks will fire
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 1
        assert cleanup_step.call_count == 0

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], states.StateType)),
        ids=lambda args: f"{args[0].name if args[0] else None} => {args[1].name}",
    )
    async def test_nested_valid_rules_fire_hooks(
        self, session, task_run, intended_transition
    ):
        side_effects = 0
        first_before_hook = MagicMock()
        second_before_hook = MagicMock()
        first_after_hook = MagicMock()
        second_after_hook = MagicMock()
        cleanup_step = MagicMock()

        # both of the rules produce side-effects on entry and exit, which we can test for

        class FirstMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                first_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                first_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                cleanup_step()

        class SecondMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                second_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                second_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                cleanup_step()

        # both rules are valid
        initial_state_type, proposed_state_type = intended_transition
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        # an ExitStack is a python builtin contstruction that allows us to
        # nest an arbitrary number of contexts (and therefore, rules), in this test
        # we'll enter the contexts one by one so we can follow what's happening
        async with contextlib.AsyncExitStack() as stack:
            # each rule receives a context as an argument and yields it back after
            # entering its context--this way we can thread a common context
            # through a series of nested rules
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
        # none of the rules fizzled, so the cleanup step is never called and side-effects are preserved
        assert side_effects == 4
        assert first_before_hook.call_count == 1
        assert first_after_hook.call_count == 1
        assert second_before_hook.call_count == 1
        assert second_after_hook.call_count == 1
        assert cleanup_step.call_count == 0

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], states.StateType)),
        ids=lambda args: f"{args[0].name if args[0] else None} => {args[1].name}",
    )
    async def test_complex_nested_rules_interact_sensibly(
        self, session, task_run, intended_transition
    ):
        side_effects = 0
        first_before_hook = MagicMock()
        mutator_before_hook = MagicMock()
        invalid_before_hook = MagicMock()
        first_after_hook = MagicMock()
        mutator_after_hook = MagicMock()
        invalid_after_hook = MagicMock()
        cleanup_after_fizzling = MagicMock()
        mutator_cleanup = MagicMock()
        invalid_cleanup = MagicMock()

        # some of the rules produce side-effects on entry and exit, but also clean up on fizzling
        # because one of the rules modifies the intended transition and itself doesn't produce side-effects
        # we should see no side effects after exiting the rule contexts

        class FirstMinimalRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                first_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                first_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                cleanup_after_fizzling()

        class StateMutatingRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {
                            initial_state.type if initial_state else None,
                            proposed_state.type,
                        }
                    )
                )
                mutator_before_hook()
                await self.reject_transition(
                    mutated_state, reason="testing my dear watson"
                )

            async def after_transition(self, initial_state, validated_state, context):
                mutator_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                mutator_cleanup()

        class InvalidatedRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                invalid_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                invalid_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                invalid_cleanup()

        # all rules start valid
        initial_state_type, proposed_state_type = intended_transition
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        # an ExitStack is a python builtin contstruction that allows us to
        # nest an arbitrary number of contexts (and therefore, rules), in this test
        # we'll enter the contexts one by one so we can follow what's happening
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

            # since no rules have had a chance to clean up, we can still
            # observe the side-effect produced by the first rule
            assert side_effects == 1

        # an ExitStack exits contexts in the reverse order in which they were called

        # once invalid always invalid--the invalid rule fires no hooks at all
        assert await invalidated_rule.invalid() is True
        assert await invalidated_rule.fizzled() is False
        assert invalid_before_hook.call_count == 0
        assert invalid_after_hook.call_count == 0
        assert invalid_cleanup.call_count == 0

        # the rule responsible for the mutation "knows about" the change to the proposed state, and remains valid
        assert await mutator_rule.invalid() is False
        assert await mutator_rule.fizzled() is False
        assert mutator_before_hook.call_count == 1
        assert mutator_after_hook.call_count == 1
        assert mutator_cleanup.call_count == 0

        # the first rule did not expect the proposed state to change, so the rule fizzles
        # instead of firing the after-transition hook, the rule cleans up after itself
        assert await first_rule.invalid() is False
        assert await first_rule.fizzled() is True
        assert first_before_hook.call_count == 1
        assert first_after_hook.call_count == 0
        assert cleanup_after_fizzling.call_count == 1

        # because all fizzled rules cleaned up and invalid rules never fire, side-effects have been undone
        assert side_effects == 0


class TestBaseUniversalRule:
    async def test_universal_rules_are_context_managers(self, session, task_run):
        side_effect = 0

        class IllustrativeUniversalRule(BaseUniversalRule):
            # Like OrchestrationRules, UniversalRules are context managers, but stateless.
            # They fire on every transition, and don't care if the intended transition is modified
            # thus, they do not have a cleanup step.

            # UniversalRules are typically used for essential bookkeeping

            # a before-transition hook that fires upon entering the rule
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                return proposed_state

            # an after-transition hook that fires after a state is validated and committed to the DB
            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1

        intended_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)
        initial_state_type, proposed_state_type = intended_transition
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        rule_as_context_manager = IllustrativeUniversalRule(ctx, *intended_transition)
        context_call = MagicMock()

        # rules govern logic by being used as a context manager
        async with rule_as_context_manager as ctx:
            context_call()

        assert context_call.call_count == 1
        assert side_effect == 2

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], states.StateType)),
        ids=lambda args: f"{args[0].name if args[0] else None} => {args[1].name}",
    )
    async def test_universal_rules_always_fire(
        self, session, task_run, intended_transition
    ):
        side_effect = 0
        before_hook = MagicMock()
        after_hook = MagicMock()

        class IllustrativeUniversalRule(BaseUniversalRule):
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                before_hook()

            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                after_hook()

        initial_state_type, proposed_state_type = intended_transition
        initial_state = await create_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = await create_task_run_state(
            session, task_run, proposed_state_type
        )

        ctx = OrchestrationContext(
            initial_state=initial_state,
            proposed_state=proposed_state,
            session=session,
            run=schemas.core.TaskRun.from_orm(task_run),
            task_run_id=task_run.id,
        )

        universal_rule = IllustrativeUniversalRule(ctx, *intended_transition)

        async with universal_rule as ctx:
            mutated_state = proposed_state.copy()
            mutated_state.type = random.choice(
                list(set(states.StateType) - set(intended_transition))
            )
            ctx.initial_state = mutated_state

        assert side_effect == 2
        assert before_hook.call_count == 1
        assert after_hook.call_count == 1
