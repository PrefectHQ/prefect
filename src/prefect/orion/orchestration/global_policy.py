from collections import defaultdict
from prefect.orion.schemas import states
from prefect.orion.orchestration.rules import (
    BaseUniversalRule,
    OrchestrationContext,
    ALL_ORCHESTRATION_STATES,
)
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy


class GlobalPolicy(BaseOrchestrationPolicy):
    REGISTERED_RULES = []
    TRANSITION_TABLE = defaultdict(list)

    def priority():
        return [
            UpdateRunDetails,
            UpdateStateDetails,
        ]


@GlobalPolicy.register
class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> states.State:
        proposed_state.run_details = states.update_run_details(
            from_state=initial_state,
            to_state=proposed_state,
        )
        return proposed_state


@GlobalPolicy.register
class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> states.State:
        proposed_state.state_details.flow_run_id = context.flow_run_id
        proposed_state.state_details.task_run_id = context.task_run_id
        return proposed_state
