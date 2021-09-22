import datetime
from typing import Union
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseUniversalRule,
    OrchestrationContext,
)
from prefect.orion.schemas import states
from prefect.orion.models import orm


class GlobalPolicy(BaseOrchestrationPolicy):
    def priority():
        return [
            SetRunStateType,
            SetStartTime,
            SetEndTime,
            IncrementRunCount,
            IncrementRunTime,
            SetExpectedStartTime,
            SetNextScheduledStartTime,
        ]


class SetRunStateType(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:

        # record the new state's type
        context.run.state_type = context.proposed_state.type


class SetStartTime(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:
        # if entering a running state and no start time is set...
        if context.proposed_state.is_running() and context.run.start_time is None:
            # set the start time
            context.run.start_time = context.proposed_state.timestamp


class SetEndTime(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:
        # if exiting a final state for a non-final state...
        if (
            context.initial_state
            and context.initial_state.is_final()
            and not context.proposed_state.is_final()
        ):
            # clear the end time
            context.run.end_time = None

        # if entering a final state...
        if context.proposed_state.is_final():
            # if the run has a start time and no end time, give it one
            if context.run.start_time and not context.run.end_time:
                context.run.end_time = context.proposed_state.timestamp


class IncrementRunTime(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:
        # if exiting a running state...
        if context.initial_state and context.initial_state.is_running():
            # increment the run time by the time spent in the previous state
            context.run.total_run_time += (
                context.proposed_state.timestamp - context.initial_state.timestamp
            )


class IncrementRunCount(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:
        # if entering a running state...
        if context.proposed_state.is_running():
            # increment the run count
            context.run.run_count += 1


class SetExpectedStartTime(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:

        # set expected start time if this is the first state
        if not context.run.expected_start_time:
            if context.proposed_state.is_scheduled():
                context.run.expected_start_time = (
                    context.proposed_state.state_details.scheduled_time
                )
            else:
                context.run.expected_start_time = context.proposed_state.timestamp


class SetNextScheduledStartTime(BaseUniversalRule):
    async def before_transition(self, context: OrchestrationContext) -> None:

        # remove the next scheduled start time if exiting a scheduled state
        if context.initial_state and context.initial_state.is_scheduled():
            context.run.next_scheduled_start_time = None

        # set next scheduled start time if entering a scheduled state
        if context.proposed_state.is_scheduled():
            context.run.next_scheduled_start_time = (
                context.proposed_state.state_details.scheduled_time
            )
