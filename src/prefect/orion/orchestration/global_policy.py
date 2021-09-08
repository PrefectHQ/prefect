from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseUniversalRule,
    OrchestrationContext,
)
from prefect.orion.schemas import states, core
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

        initial_state = context.initial_state
        proposed_state = context.proposed_state

        # avoid mutation inplace
        run_details = run.run_details.copy()  # type: core.RunDetails

        # -- record the new state's details
        run_details.state_id = proposed_state.id
        run_details.state_type = proposed_state.type

        # -- compute duration
        if initial_state:
            state_duration = (
                proposed_state.timestamp - initial_state.timestamp
            ).total_seconds()
        else:
            state_duration = 0

        # -- set next scheduled start time
        if proposed_state.is_scheduled():
            run_details.next_scheduled_start_time = (
                proposed_state.state_details.scheduled_time
            )

        # -- set expected start time if this is the first state
        if not run_details.expected_start_time:
            if proposed_state.is_scheduled():
                run_details.expected_start_time = run_details.next_scheduled_start_time
            else:
                run_details.expected_start_time = proposed_state.timestamp

        # -- update duration if there's a start time
        if run_details.start_time:
            # increment the total duration
            run_details.total_time_seconds += state_duration

        # -- if exiting a running state...
        if initial_state and initial_state.is_running():
            # increment the "run_time_seconds"
            run_details.total_run_time_seconds += state_duration

        # -- if entering a running state...
        if proposed_state.is_running():
            # increment the run count
            run_details.run_count += 1
            # set the start time
            if run_details.start_time is None:
                run_details.start_time = proposed_state.timestamp

        # -- if entering a final state...
        if proposed_state.is_final():
            # if the run started, give it an end time (unless it has one)
            if run_details.start_time and not run_details.end_time:
                run_details.end_time = proposed_state.timestamp

        # -- if exiting a final state...
        if initial_state and initial_state.is_final():
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
        if context.proposed_state is not None:
            context.proposed_state.state_details.flow_run_id = context.flow_run_id
            context.proposed_state.state_details.task_run_id = context.task_run_id
