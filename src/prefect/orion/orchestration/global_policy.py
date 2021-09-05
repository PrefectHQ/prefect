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


class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        context: OrchestrationContext,
    ) -> states.State:
        if context.run_type == "flow_run":
            run = await context.session.get(orm.FlowRun, context.flow_run_id)
        else:
            run = await context.session.get(orm.TaskRun, context.task_run_id)
        if not run:
            raise ValueError("Run not found.")

        # avoid mutation inplace
        run_details = run.run_details.copy()

        # record the new state's details
        run_details.current_state_id = context.proposed_state.id
        run_details.current_state_type = context.proposed_state.type

        # compute duration
        if context.initial_state:
            state_duration = (
                context.proposed_state.timestamp - context.initial_state.timestamp
            ).total_seconds()
        else:
            state_duration = 0

        # update duration if there's a start time
        if run_details.start_time:
            # increment the total duration
            run_details.total_time_seconds += state_duration

        # if exiting a running state...
        if context.initial_state and context.initial_state.is_running():
            # increment the "run_time_seconds"
            run_details.total_run_time_seconds += state_duration

        # if entering a running state...
        if context.proposed_state.is_running():
            # increment the run count
            run_details.run_count += 1
            # set the start time
            if run_details.start_time is None:
                run_details.start_time = context.proposed_state.timestamp

        # if entering a final state...
        if context.proposed_state.is_final():
            # if the run started, give it an end time (unless it has one)
            if run_details.start_time and not run_details.end_time:
                run_details.end_time = context.proposed_state.timestamp

        # if exiting a final state...
        if context.initial_state and context.initial_state.is_final():
            # clear the end time
            run_details.end_time = None

        # set the run details on the orm object
        # to be tracked by the active session
        run.run_details = run_details


class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        context: OrchestrationContext,
    ) -> states.State:
        context.proposed_state.state_details.flow_run_id = context.flow_run_id
        context.proposed_state.state_details.task_run_id = context.task_run_id
