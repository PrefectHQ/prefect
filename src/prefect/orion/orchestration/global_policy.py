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
            UpdateRunDetails,
            UpdateStateDetails,
        ]


def update_run_details(
    initial_state: ALL_ORCHESTRATION_STATES,
    proposed_state: ALL_ORCHESTRATION_STATES,
    run: Union[orm.FlowRun, orm.TaskRun],
):

    # -- record the new state's details
    run.state_type = proposed_state.type

    # -- compute duration
    if initial_state:
        state_duration = proposed_state.timestamp - initial_state.timestamp
    else:
        state_duration = datetime.timedelta(0)

    # -- set next scheduled start time
    if proposed_state.is_scheduled():
        run.next_scheduled_start_time = proposed_state.state_details.scheduled_time

    # -- set expected start time if this is the first state
    if not run.expected_start_time:
        if proposed_state.is_scheduled():
            run.expected_start_time = run.next_scheduled_start_time
        else:
            run.expected_start_time = proposed_state.timestamp

    # -- if exiting a running state...
    if initial_state and initial_state.is_running():
        # increment the run time
        run.total_run_time += state_duration

    # -- if entering a running state...
    if proposed_state.is_running():
        # increment the run count
        run.run_count += 1
        # set the start time
        if run.start_time is None:
            run.start_time = proposed_state.timestamp

    # -- if entering a final state...
    if proposed_state.is_final():
        # if the run started, give it an end time (unless it has one)
        if run.start_time and not run.end_time:
            run.end_time = proposed_state.timestamp

    # -- if exiting a final state...
    if initial_state and initial_state.is_final():
        # clear the end time
        run.end_time = None


class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        context: OrchestrationContext,
    ) -> states.State:

        # if no state transition is taking place, exit
        if context.proposed_state is None:
            return

        update_run_details(
            initial_state=context.initial_state,
            proposed_state=context.proposed_state,
            run=context.run,
        )


class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        context: OrchestrationContext,
    ) -> states.State:
        flow_run = await context.flow_run
        task_run = await context.task_run
        context.proposed_state.state_details.flow_run_id = flow_run.id
        if task_run:
            context.proposed_state.state_details.task_run_id = task_run.id
