import contextlib
import datetime
import random
import sqlite3
from itertools import product
from unittest.mock import MagicMock

import pytest
import sqlalchemy.exc

from prefect.server import models, schemas
from prefect.server.database import provide_database_interface
from prefect.server.exceptions import OrchestrationError
from prefect.server.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseOrchestrationRule,
    BaseUniversalTransform,
    OrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.server.schemas import states
from prefect.server.schemas.responses import (
    OrchestrationResult,
    SetStateStatus,
    StateAbortDetails,
    StateRejectDetails,
    StateWaitDetails,
)
from prefect.testing.utilities import AsyncMock
from prefect.types._datetime import now

# Convert constant from set to list for deterministic ordering of tests
ALL_ORCHESTRATION_STATES = list(
    sorted(ALL_ORCHESTRATION_STATES, key=lambda item: str(item))
    # Set the key to sort the `None` state
)


async def commit_task_run_state(
    session, task_run, state_type: states.StateType, state_details=None, state_name=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    if (
        state_type == states.StateType.SCHEDULED
        and "scheduled_time" not in state_details
    ):
        state_details.update({"scheduled_time": now("UTC")})

    new_state = schemas.states.State(
        type=state_type,
        timestamp=now("UTC") - datetime.timedelta(seconds=5),
        state_details=state_details,
        name=state_name,
    )

    db = provide_database_interface()
    orm_state = db.TaskRunState(
        task_run_id=task_run.id,
        **new_state.orm_dict(),
    )

    task_run.state = orm_state
    session.add(orm_state)

    await session.flush()
    return orm_state.as_state()


def transition_names(transition):
    initial = f"{transition[0].name if transition[0] else None}"
    proposed = f" => {transition[1].name if transition[1] else None}"
    return initial + proposed


class TestOrchestrationResult:
    @pytest.mark.parametrize(
        ["response_type", "response_details"],
        [
            (StateWaitDetails, StateWaitDetails(delay_seconds=20, reason="No!")),
            (StateRejectDetails, StateRejectDetails(reason="I don't want to change!")),
            (StateAbortDetails, StateAbortDetails(reason="I don't need to change!")),
        ],
        ids=["wait", "reject", "abort"],
    )
    async def test_details_are_not_improperly_coerced(
        self, response_type, response_details
    ):
        status = SetStateStatus.ACCEPT
        cast_result = OrchestrationResult(
            state=None, status=status, details=response_details.model_dump()
        )
        assert isinstance(cast_result.details, response_type)


class TestBaseOrchestrationRule:
    async def test_orchestration_rules_are_context_managers(self, session, task_run):
        side_effect = 0

        class IllustrativeRule(BaseOrchestrationRule):
            # we implement rules by inheriting from `BaseOrchestrationRule`
            # in order to do so, we need to define three methods:

            # when creating a rule, we need to specify lists of valid
            # state types the rule can operate on
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            # a before-transition hook that fires upon entering the rule, returns None
            # and is the only opportunity for a rule to modify the state transition
            # by calling a state mutation method like `self.reject_transision`
            async def before_transition(
                self, initial_state, proposed_state, context
            ) -> None:
                nonlocal side_effect
                side_effect += 1

            # an after-transition hook that returns None, fires after a state
            # is validated and committed to the DB
            async def after_transition(
                self, initial_state, validated_state, context
            ) -> None:
                nonlocal side_effect
                side_effect += 1

            # the cleanup step returns None, and allows a rule to revert side-effects caused
            # by the before-transition hook in case the transition does not complete
            async def cleanup(self, initial_state, validated_state, context) -> None:
                nonlocal side_effect
                side_effect -= 1

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # rules are valid if the initial and proposed state always match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

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
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        fizzling_rule = FizzlingRule(ctx, *intended_transition)
        async with fizzling_rule as ctx:
            # within the context, only the before-hook has fired and we can observe the side-effect
            assert side_effect == 1

            # mutating the proposed state inside the context will fizzle the rule
            mutated_state = proposed_state.model_copy()
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

    async def test_rules_that_reject_state_do_not_fizzle_themselves(
        self, session, task_run
    ):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.model_copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {initial_state.type, proposed_state.type}
                    )
                )
                before_transition_hook()
                # `BaseOrchestrationRule` provides hooks designed to mutate the proposed state
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
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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

    async def test_rules_that_wait_do_not_fizzle_themselves(self, session, task_run):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.model_copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {initial_state.type, proposed_state.type}
                    )
                )
                before_transition_hook()
                # `BaseOrchestrationRule` provides hooks designed to mutate the proposed state
                await self.delay_transition(42, reason="for testing, of course")

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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

    async def test_rules_that_abort_do_not_fizzle_themselves(self, session, task_run):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class StateMutatingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state = proposed_state.model_copy()
                mutated_state.type = random.choice(
                    list(
                        set(states.StateType)
                        - {initial_state.type, proposed_state.type}
                    )
                )
                before_transition_hook()
                # `BaseOrchestrationRule` provides hooks designed to mutate the proposed state
                await self.abort_transition(reason="for testing, of course")

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
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

    async def test_rules_can_pass_parameters_via_context(self, session, task_run):
        before_transition_hook = MagicMock()
        special_message = None

        class MessagePassingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                await self.update_context_parameters("a special message", "hello!")
                # context parameters should not be sensitive to mutation
                context.parameters["a special message"] = "I can't hear you"

        class MessageReadingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()
                nonlocal special_message
                special_message = context.parameters["a special message"]

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = states.State(type=proposed_state_type)

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        message_passer = MessagePassingRule(ctx, *intended_transition)
        async with message_passer as ctx:
            message_reader = MessageReadingRule(ctx, *intended_transition)
            async with message_reader as ctx:
                pass

        assert before_transition_hook.call_count == 1
        assert special_message == "hello!"

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [*states.StateType])),
        ids=transition_names,
    )
    async def test_rules_that_raise_exceptions_during_before_transition(
        self, session, task_run, intended_transition
    ):
        outer_before_transition_hook = MagicMock()
        before_transition_hook = MagicMock()
        outer_after_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        outer_cleanup_step = MagicMock()
        cleanup_step = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                outer_before_transition_hook()

            async def after_transition(self, initial_state, validated_state, context):
                outer_after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                outer_cleanup_step()

        class RaisingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook()
                raise RuntimeError("Test!")

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type, proposed_state_type = intended_transition
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = TaskOrchestrationContext(
            session=session,
            run=task_run,
            initial_state=initial_state,
            proposed_state=proposed_state,
        )

        async with contextlib.AsyncExitStack() as stack:
            minimal_rule = MinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(minimal_rule)

            raising_rule = RaisingRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(raising_rule)

        assert ctx.proposed_state is None, "Proposed state should be None"

        assert await minimal_rule.fizzled() is True

        assert await raising_rule.invalid() is False, (
            "Rules that error on entry should be fizzled so they can try and clean up"
        )
        assert await raising_rule.fizzled() is True

        assert outer_before_transition_hook.call_count == 1
        assert outer_after_transition_hook.call_count == 0
        assert outer_cleanup_step.call_count == 1, (
            "All rules should clean up side effects"
        )

        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 0, (
            "The after-transition hook should not run"
        )
        assert cleanup_step.call_count == 1, "All rules should clean up side effects"
        assert isinstance(ctx.orchestration_error, RuntimeError)

    @pytest.mark.parametrize("initial_state_type", ALL_ORCHESTRATION_STATES)
    async def test_rules_enforce_initial_state_validity(
        self, session, task_run, initial_state_type
    ):
        proposed_state_type = None
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        pre_transition_hook = MagicMock()
        post_transition_hook = MagicMock()

        class StateEnforcingRule(BaseOrchestrationRule):
            FROM_STATES = set(ALL_ORCHESTRATION_STATES) - {initial_state_type}
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                pre_transition_hook()

            async def after_transition(self, initial_state, validated_state, context):
                post_transition_hook()

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        state_enforcing_rule = StateEnforcingRule(ctx, *intended_transition)
        async with state_enforcing_rule as ctx:
            pass
        assert await state_enforcing_rule.invalid()
        assert pre_transition_hook.call_count == 0
        assert post_transition_hook.call_count == 0

    @pytest.mark.parametrize("proposed_state_type", ALL_ORCHESTRATION_STATES)
    async def test_rules_enforce_proposed_state_validity(
        self, session, task_run, proposed_state_type
    ):
        initial_state_type = None
        intended_transition = (initial_state_type, proposed_state_type)
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        pre_transition_hook = MagicMock()
        post_transition_hook = MagicMock()

        class StateEnforcingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = set(ALL_ORCHESTRATION_STATES) - {proposed_state_type}

            async def before_transition(self, initial_state, proposed_state, context):
                pre_transition_hook()

            async def after_transition(self, initial_state, validated_state, context):
                post_transition_hook()

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        state_enforcing_rule = StateEnforcingRule(ctx, *intended_transition)
        async with state_enforcing_rule as ctx:
            pass
        assert await state_enforcing_rule.invalid()
        assert pre_transition_hook.call_count == 0
        assert post_transition_hook.call_count == 0

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [*states.StateType, None])),
        ids=transition_names,
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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

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
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        # an ExitStack is a python builtin construction that allows us to
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
        list(product([*states.StateType, None], [*states.StateType, None])),
        ids=transition_names,
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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

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
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself upon exiting
                mutated_state_type = random.choice(
                    list(
                        set(states.StateType)
                        - {
                            initial_state.type if initial_state else None,
                            proposed_state.type if proposed_state else None,
                        }
                    )
                )
                mutated_state = await commit_task_run_state(
                    session, task_run, mutated_state_type
                )
                mutator_before_hook()
                # `BaseOrchestrationRule` provides hooks designed to mutate the proposed state
                await self.reject_transition(
                    mutated_state, reason="testing my dear watson"
                )

            async def after_transition(self, initial_state, validated_state, context):
                mutator_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                mutator_cleanup()

        class InvalidatedRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

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
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        # an ExitStack is a python builtin construction that allows us to
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


class TestBaseUniversalTransform:
    async def test_universal_transforms_are_context_managers(self, session, task_run):
        side_effect = 0

        class IllustrativeUniversalTransform(BaseUniversalTransform):
            # Like OrchestrationRules, UniversalTrnasforms are context managers, but
            # stateless. They fire on every transition, and don't care if the intended
            # transition is modified thus, they do not have a cleanup step.

            # UniversalTransforms are typically used for essential bookkeeping

            # a before-transition hook that fires upon entering the rule
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1

            # an after-transition hook that fires after a state is validated and
            # committed to the DB
            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1

        intended_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)
        initial_state_type, proposed_state_type = intended_transition
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        xform_as_context_manager = IllustrativeUniversalTransform(
            ctx, *intended_transition
        )
        context_call = MagicMock()

        async with xform_as_context_manager as ctx:
            context_call()

        assert context_call.call_count == 1
        assert side_effect == 2

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [*states.StateType])),
        ids=transition_names,
    )
    async def test_universal_transforms_always_fire_on_all_transitions(
        self, session, task_run, intended_transition
    ):
        side_effect = 0
        before_hook = MagicMock()
        after_hook = MagicMock()

        class IllustrativeUniversalTransform(BaseUniversalTransform):
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                before_hook()

            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                after_hook()

        initial_state_type, proposed_state_type = intended_transition
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        universal_transform = IllustrativeUniversalTransform(ctx, *intended_transition)

        async with universal_transform as ctx:
            mutated_state_type = random.choice(
                list(set(states.StateType) - set(intended_transition))
            )
            mutated_state = await commit_task_run_state(
                session, task_run, mutated_state_type
            )
            ctx.initial_state = mutated_state

        assert side_effect == 2
        assert before_hook.call_count == 1
        assert after_hook.call_count == 1

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [None])),
        ids=transition_names,
    )
    async def test_universal_transforms_always_fire_on_nullified_transitions(
        self, session, task_run, intended_transition
    ):
        # nullified transitions occur when the proposed state becomes None
        # and nothing is written to the database

        side_effect = 0
        before_hook = MagicMock()
        after_hook = MagicMock()

        class IllustrativeUniversalTransform(BaseUniversalTransform):
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                before_hook()

            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                after_hook()

        initial_state_type, proposed_state_type = intended_transition
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        universal_transform = IllustrativeUniversalTransform(ctx, *intended_transition)

        async with universal_transform as ctx:
            mutated_state_type = random.choice(
                list(set(states.StateType) - set(intended_transition))
            )
            mutated_state = await commit_task_run_state(
                session, task_run, mutated_state_type
            )
            ctx.initial_state = mutated_state

        assert side_effect == 2
        assert before_hook.call_count == 1
        assert after_hook.call_count == 1

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [*states.StateType])),
        ids=transition_names,
    )
    async def test_universal_transforms_never_fire_after_transition_on_errored_transitions(
        self, session, task_run, intended_transition
    ):
        # nullified transitions occur when the proposed state becomes None
        # and nothing is written to the database

        side_effect = 0
        before_hook = MagicMock()
        after_hook = MagicMock()

        class IllustrativeUniversalTransform(BaseUniversalTransform):
            async def before_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                before_hook()

            async def after_transition(self, context):
                nonlocal side_effect
                side_effect += 1
                after_hook()

        initial_state_type, proposed_state_type = intended_transition
        initial_state = await commit_task_run_state(
            session, task_run, initial_state_type
        )
        proposed_state = (
            states.State(type=proposed_state_type) if proposed_state_type else None
        )

        ctx = OrchestrationContext(
            session=session,
            initial_state=initial_state,
            proposed_state=proposed_state,
            run=task_run,
        )

        universal_transform = IllustrativeUniversalTransform(ctx, *intended_transition)

        async with universal_transform as ctx:
            ctx.orchestration_error = Exception

        assert side_effect == 1
        assert before_hook.call_count == 1
        assert after_hook.call_count == 0, (
            "after_transition should not be called if orchestration encountered errors."
        )


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestOrchestrationContext:
    async def test_context_is_protected_from_mutation_at_all_costs(
        self, session, run_type, initialize_orchestration
    ):
        class EvilVillainRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                context.initial_state.type = states.StateType.CANCELLED
                context.proposed_state.type = states.StateType.COMPLETED

            async def after_transition(self, initial_state, validated_state, context):
                context.initial_state.type = states.StateType.CANCELLED
                context.proposed_state.type = states.StateType.COMPLETED
                context.validated_state.type = states.StateType.SCHEDULED

        class MutatingSlimeRule(BaseOrchestrationRule):
            async def before_transition(self, initial_state, proposed_state, context):
                initial_state.type = states.StateType.CANCELLED
                proposed_state.type = states.StateType.COMPLETED

            async def after_transition(self, initial_state, validated_state, context):
                initial_state.type = states.StateType.CANCELLED
                validated_state.type = states.StateType.COMPLETED

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            the_evil_villain = EvilVillainRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(the_evil_villain)
            assert ctx.initial_state_type == states.StateType.PENDING
            assert ctx.proposed_state_type == states.StateType.RUNNING
            # foiled again

            the_mutating_slime = MutatingSlimeRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(the_mutating_slime)
            assert ctx.initial_state_type == states.StateType.PENDING
            assert ctx.proposed_state_type == states.StateType.RUNNING
            # thankfully we had the antidote
            await ctx.validate_proposed_state()

        # check that the states remain the same after exiting the context
        # our context emerges unscathed
        assert ctx.initial_state_type == states.StateType.PENDING
        assert ctx.proposed_state_type == states.StateType.RUNNING
        assert ctx.validated_state_type == states.StateType.RUNNING

    async def test_context_will_mutate_if_asked_politely(
        self, session, run_type, initialize_orchestration
    ):
        class PoliteHeroRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.reject_transition(
                    proposed_state, reason="heroes ask permission"
                )

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            the_polite_hero = PoliteHeroRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(the_polite_hero)
            await ctx.validate_proposed_state()

        assert ctx.proposed_state_type == states.StateType.COMPLETED
        assert ctx.validated_state_type == states.StateType.COMPLETED

    async def test_context_will_not_mutate_if_asked_too_late(
        self, session, run_type, initialize_orchestration
    ):
        class TardyHeroRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def after_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.reject_transition(
                    proposed_state, reason="heroes should not be late"
                )

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        # oh no, the hero is too late
        with pytest.raises(RuntimeError):
            async with contextlib.AsyncExitStack() as stack:
                the_tardy_hero = TardyHeroRule(ctx, *intended_transition)
                ctx = await stack.enter_async_context(the_tardy_hero)
                await ctx.validate_proposed_state()

    @pytest.mark.parametrize("delay", [42, 424242])
    async def test_context_will_propose_no_state_if_asked_to_wait(
        self, session, run_type, initialize_orchestration, delay
    ):
        class WaitingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.delay_transition(delay, reason="heroes should not be late")

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            the_tardy_hero = WaitingRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(the_tardy_hero)
            await ctx.validate_proposed_state()

        assert ctx.proposed_state is None
        assert ctx.response_status == schemas.responses.SetStateStatus.WAIT
        assert ctx.response_details.delay_seconds == delay

    @pytest.mark.parametrize("delay", [42, 424242])
    async def test_rules_cant_try_to_wait_after_validation(
        self, session, run_type, initialize_orchestration, delay
    ):
        class WaitingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def after_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.delay_transition(delay, reason="heroes should not be late")

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        with pytest.raises(RuntimeError):
            async with contextlib.AsyncExitStack() as stack:
                the_tardy_hero = WaitingRule(ctx, *intended_transition)
                ctx = await stack.enter_async_context(the_tardy_hero)
                await ctx.validate_proposed_state()

        assert ctx.validated_state_type is states.StateType.RUNNING
        assert ctx.response_status == schemas.responses.SetStateStatus.ACCEPT

    async def test_context_will_propose_no_state_if_aborted(
        self, session, run_type, initialize_orchestration
    ):
        class AbortingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.abort_transition(reason="stop the transition if possible")

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            aborting_rule = AbortingRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(aborting_rule)
            intitial_state = ctx.run.state
            await ctx.validate_proposed_state()

        assert ctx.proposed_state is None
        assert ctx.validated_state == intitial_state.as_state()
        assert ctx.response_status == schemas.responses.SetStateStatus.ABORT

    async def test_rules_cant_abort_after_validation(
        self, session, run_type, initialize_orchestration
    ):
        class WaitingRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def after_transition(self, initial_state, proposed_state, context):
                proposed_state.type = states.StateType.COMPLETED
                await self.abort_transition(reason="stop the transition if possible")

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        with pytest.raises(RuntimeError):
            async with contextlib.AsyncExitStack() as stack:
                aborting_rule = WaitingRule(ctx, *intended_transition)
                ctx = await stack.enter_async_context(aborting_rule)
                await ctx.validate_proposed_state()

        assert ctx.validated_state_type is states.StateType.RUNNING
        assert ctx.response_status == schemas.responses.SetStateStatus.ACCEPT

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType, None], [*states.StateType, None])),
        ids=transition_names,
    )
    async def test_contexts_validate_proposed_states(
        self, session, run_type, initialize_orchestration, intended_transition
    ):
        initial_state_type, proposed_state_type = intended_transition
        ctx = await initialize_orchestration(session, run_type, *intended_transition)
        assert ctx.validated_state is None
        await ctx.validate_proposed_state()

        if proposed_state_type is not None:
            assert ctx.validated_state_type == ctx.proposed_state_type
        else:
            assert ctx.validated_state_type == initial_state_type

    async def test_context_validation_returns_none(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)
        assert await ctx.validate_proposed_state() is None

    async def test_context_validation_sets_run_state(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        assert ctx.run.state.id != ctx.proposed_state.id
        await ctx.validate_proposed_state()
        assert ctx.run.state.id == ctx.validated_state.id
        assert ctx.validated_state.id == ctx.proposed_state.id

    async def test_context_validation_writes_result_artifact(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)
        ctx.proposed_state.data = {"value": "some special data"}

        assert ctx.run.state.id != ctx.proposed_state.id
        await ctx.validate_proposed_state()
        assert ctx.run.state.id == ctx.validated_state.id
        assert ctx.validated_state.id == ctx.proposed_state.id
        assert ctx.validated_state.data == {"value": "some special data"}, (
            "result data should be attached to the validated state"
        )

        # an artifact should be created with the result data as well
        if run_type == "task":
            state_reader = models.task_run_states.read_task_run_state
        else:
            state_reader = models.flow_run_states.read_flow_run_state
        validated_orm_state = await state_reader(ctx.session, ctx.validated_state.id)
        artifact_id = validated_orm_state.result_artifact_id

        orm_artifact = await models.artifacts.read_artifact(ctx.session, artifact_id)
        assert orm_artifact.data == {"value": "some special data"}

        if run_type == "task":
            assert orm_artifact.task_run_id == ctx.run.id
            assert orm_artifact.flow_run_id == ctx.run.flow_run_id
        else:
            assert orm_artifact.flow_run_id == ctx.run.id

    async def test_context_validation_writes_result_artifact_with_metadata(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)
        ctx.proposed_state.data = dict(
            value="some special data",
            artifact_type="a special type",
            artifact_description="it's so pretty",
        )

        assert ctx.run.state.id != ctx.proposed_state.id
        await ctx.validate_proposed_state()
        assert ctx.run.state.id == ctx.validated_state.id
        assert ctx.validated_state.id == ctx.proposed_state.id
        assert ctx.validated_state.data == {"value": "some special data"}, (
            "sanitized result data should be attached to the validated state"
        )

        # an artifact should be created with the result data as well
        if run_type == "task":
            state_reader = models.task_run_states.read_task_run_state
        else:
            state_reader = models.flow_run_states.read_flow_run_state
        validated_orm_state = await state_reader(ctx.session, ctx.validated_state.id)
        artifact_id = validated_orm_state.result_artifact_id

        orm_artifact = await models.artifacts.read_artifact(ctx.session, artifact_id)
        assert orm_artifact.data == {"value": "some special data"}
        assert orm_artifact.type == "a special type"
        assert orm_artifact.description == "it's so pretty"

    async def test_context_validation_does_not_write_artifact_when_no_result(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)
        ctx.proposed_state.data = None

        assert ctx.run.state.id != ctx.proposed_state.id
        await ctx.validate_proposed_state()
        assert ctx.run.state.id == ctx.validated_state.id
        assert ctx.validated_state.id == ctx.proposed_state.id
        assert ctx.validated_state.data is None, (
            "this validated state should have no result"
        )

        # an artifact should be created with the result data as well
        if run_type == "task":
            state_reader = models.task_run_states.read_task_run_state
        else:
            state_reader = models.flow_run_states.read_flow_run_state
        validated_orm_state = await state_reader(ctx.session, ctx.validated_state.id)
        artifact_id = validated_orm_state.result_artifact_id
        assert artifact_id is None

        orm_artifact = await models.artifacts.read_artifact(ctx.session, artifact_id)
        assert orm_artifact is None

    async def test_context_state_validation_encounters_exception(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_hook = MagicMock()

        class MockRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook(initial_state, proposed_state, context)

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook(initial_state, validated_state, context)

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_hook(initial_state, validated_state, context)

        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        # Bypass pydantic mutation protection, inject an error
        object.__setattr__(
            ctx.session, "flush", AsyncMock(side_effect=RuntimeError("One time error!"))
        )

        async with contextlib.AsyncExitStack() as stack:
            mock_rule = MockRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(mock_rule)
            await ctx.validate_proposed_state()

        before_transition_hook.assert_called_once()
        if proposed_state_type is not None:
            after_transition_hook.assert_not_called()
            (
                cleanup_hook.assert_called_once(),
                "Cleanup should be called when transition is aborted",
            )
        else:
            after_transition_hook.assert_called_once(), "Rule expected no transition"
            cleanup_hook.assert_not_called()

        assert ctx.proposed_state is None
        assert ctx.response_status == SetStateStatus.ABORT
        assert isinstance(ctx.response_details, StateAbortDetails)
        assert (
            ctx.response_details.reason
            == "Error validating state: RuntimeError('One time error!')"
        )

    async def test_context_state_validation_encounters_sqlite_busy_exception(
        self, session, run_type, initialize_orchestration
    ):
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_hook = MagicMock()

        class MockRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                before_transition_hook(initial_state, proposed_state, context)

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook(initial_state, validated_state, context)

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_hook(initial_state, validated_state, context)

        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        orig = sqlite3.OperationalError("database locked")
        setattr(orig, "sqlite_errorname", "SQLITE_BUSY")
        setattr(orig, "sqlite_errorcode", 5)

        # Bypass pydantic mutation protection, inject an error
        object.__setattr__(
            ctx.session,
            "flush",
            AsyncMock(
                side_effect=sqlalchemy.exc.OperationalError(
                    "statement",
                    {"params": 1},
                    orig,
                    Exception,
                )
            ),
        )

        with pytest.raises(sqlalchemy.exc.OperationalError):
            async with contextlib.AsyncExitStack() as stack:
                mock_rule = MockRule(ctx, *intended_transition)
                ctx = await stack.enter_async_context(mock_rule)
                await ctx.validate_proposed_state()

        before_transition_hook.assert_called_once()
        if proposed_state_type is not None:
            after_transition_hook.assert_not_called()
            (
                cleanup_hook.assert_called_once(),
                "Cleanup should be called when transition is aborted",
            )
        else:
            after_transition_hook.assert_called_once(), "Rule expected no transition"
            cleanup_hook.assert_not_called()

        assert ctx.proposed_state is None


@pytest.mark.parametrize("run_type", ["task", "flow"])
class TestNullRejection:
    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType], [*states.StateType])),
        ids=transition_names,
    )
    async def test_null_rejects_fizzle_all_prior_rules(
        self, session, initialize_orchestration, intended_transition, run_type
    ):
        side_effects = 0
        minimal_before_hook = MagicMock()
        first_after_hook = MagicMock()
        null_rejection_before_hook = MagicMock()
        minimal_after_hook = MagicMock()
        null_rejection_after_hook = MagicMock()
        minimal_cleanup_hook = MagicMock()
        null_rejection_cleanup = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                minimal_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                first_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                minimal_cleanup_hook()

        class NullRejectionRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                null_rejection_before_hook()
                await self.reject_transition(None, reason="its okay")

            async def after_transition(self, initial_state, validated_state, context):
                null_rejection_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                null_rejection_cleanup()

        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            # first enter a minimal rule that fires its pre-transition hook
            minimal_rule = MinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(minimal_rule)

            assert side_effects == 1
            minimal_before_hook.assert_called_once()
            minimal_after_hook.assert_not_called()
            minimal_cleanup_hook.assert_not_called()
            null_rejection_before_hook.assert_not_called()
            null_rejection_after_hook.assert_not_called()
            null_rejection_cleanup.assert_not_called()

            # the null rejection rule rejects the transition
            null_rejector = NullRejectionRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(null_rejector)

            assert side_effects == 1
            minimal_before_hook.assert_called_once()
            minimal_after_hook.assert_not_called()
            minimal_cleanup_hook.assert_not_called()
            null_rejection_before_hook.assert_called_once()
            null_rejection_after_hook.assert_not_called()
            null_rejection_cleanup.assert_not_called()

            await ctx.validate_proposed_state()

        assert side_effects == 0
        assert await minimal_rule.fizzled() is True
        assert await null_rejector.invalid() is False
        assert await null_rejector.fizzled() is False
        minimal_after_hook.assert_not_called()
        minimal_cleanup_hook.assert_called_once()
        assert ctx.response_status == schemas.responses.SetStateStatus.REJECT

    @pytest.mark.parametrize(
        "intended_transition",
        list(product([*states.StateType], [*states.StateType])),
        ids=transition_names,
    )
    async def test_null_rejects_abort_all_subsequent_rules(
        self, session, initialize_orchestration, intended_transition, run_type
    ):
        side_effects = 0
        minimal_before_hook = MagicMock()
        null_rejection_before_hook = MagicMock()
        minimal_after_hook = MagicMock()
        first_after_hook = MagicMock()
        null_rejection_after_hook = MagicMock()
        minimal_cleanup_hook = MagicMock()
        null_rejection_cleanup = MagicMock()

        class MinimalRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                nonlocal side_effects
                side_effects += 1
                minimal_before_hook()

            async def after_transition(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects += 1
                first_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                nonlocal side_effects
                side_effects -= 1
                minimal_cleanup_hook()

        class NullRejectionRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                null_rejection_before_hook()
                await self.reject_transition(None, reason="its okay")

            async def after_transition(self, initial_state, validated_state, context):
                null_rejection_after_hook()

            async def cleanup(self, initial_state, validated_state, context):
                null_rejection_cleanup()

        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            # the null rejection rule rejects the transition
            null_rejector = NullRejectionRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(null_rejector)

            assert side_effects == 0
            null_rejection_before_hook.assert_called_once()
            null_rejection_after_hook.assert_not_called()
            null_rejection_cleanup.assert_not_called()
            minimal_before_hook.assert_not_called()
            minimal_after_hook.assert_not_called()
            minimal_cleanup_hook.assert_not_called()

            # first enter a minimal rule that fires its pre-transition hook
            minimal_rule = MinimalRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(minimal_rule)

            assert side_effects == 0
            null_rejection_before_hook.assert_called_once()
            null_rejection_after_hook.assert_not_called()
            null_rejection_cleanup.assert_not_called()
            minimal_before_hook.assert_not_called()
            minimal_after_hook.assert_not_called()
            minimal_cleanup_hook.assert_not_called()

            await ctx.validate_proposed_state()

        assert side_effects == 0
        assert await minimal_rule.invalid() is True
        assert await null_rejector.invalid() is False
        assert await null_rejector.fizzled() is False
        minimal_after_hook.assert_not_called()
        minimal_cleanup_hook.assert_not_called()
        assert ctx.response_status == schemas.responses.SetStateStatus.REJECT

    @pytest.mark.parametrize(
        "proposed_state_type",
        list(states.StateType),
    )
    async def test_cannot_null_reject_runs_with_no_state(
        self, session, run_type, proposed_state_type, initialize_orchestration
    ):
        class NullRejectionRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                await self.reject_transition(None, reason="its okay")

        initial_state_type = None
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            null_rejector = NullRejectionRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(null_rejector)
            await ctx.validate_proposed_state()

        assert isinstance(ctx.orchestration_error, OrchestrationError)
        assert ctx.response_status == SetStateStatus.ABORT

    async def test_context_will_not_write_new_state_with_null_reject(
        self, session, run_type, initialize_orchestration
    ):
        class NullRejectionRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                await self.reject_transition(None, reason="its okay")

        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)
        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        async with contextlib.AsyncExitStack() as stack:
            reject_no_write = NullRejectionRule(ctx, *intended_transition)
            ctx = await stack.enter_async_context(reject_no_write)
            intial_state = ctx.run.state
            await ctx.validate_proposed_state()

        assert ctx.proposed_state is None
        assert ctx.validated_state == states.State.model_validate(
            intial_state, from_attributes=True
        )
        assert ctx.response_status == schemas.responses.SetStateStatus.REJECT

    async def test_rules_that_reject_state_with_null_do_not_fizzle_themselves(
        self, session, task_run, run_type, initialize_orchestration
    ):
        before_transition_hook = MagicMock()
        after_transition_hook = MagicMock()
        cleanup_step = MagicMock()

        class NullRejectionRule(BaseOrchestrationRule):
            FROM_STATES = ALL_ORCHESTRATION_STATES
            TO_STATES = ALL_ORCHESTRATION_STATES

            async def before_transition(self, initial_state, proposed_state, context):
                # this rule mutates the proposed state type, but won't fizzle itself
                # upon exiting
                before_transition_hook()
                # `BaseOrchestrationRule` provides hooks designed to mutate the proposed state
                await self.reject_transition(None, reason="for testing, of course")

            async def after_transition(self, initial_state, validated_state, context):
                after_transition_hook()

            async def cleanup(self, initial_state, validated_state, context):
                cleanup_step()

        # this rule seems valid because the initial and proposed states match the intended transition
        initial_state_type = states.StateType.PENDING
        proposed_state_type = states.StateType.RUNNING
        intended_transition = (initial_state_type, proposed_state_type)

        ctx = await initialize_orchestration(session, run_type, *intended_transition)

        null_rejector = NullRejectionRule(ctx, *intended_transition)
        async with null_rejector as ctx:
            pass

        assert await null_rejector.invalid() is False
        assert await null_rejector.fizzled() is False

        # despite the mutation, this rule is valid so before and after hooks will fire
        assert before_transition_hook.call_count == 1
        assert after_transition_hook.call_count == 1
        assert cleanup_step.call_count == 0
