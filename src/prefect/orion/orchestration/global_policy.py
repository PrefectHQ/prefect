from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseUniversalRule,
)
from prefect.orion.schemas import states


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
        # context: OrchestrationContext,
    ) -> states.State:
        self.context.proposed_state.run_details = states.update_run_details(
            from_state=self.context.initial_state,
            to_state=self.context.proposed_state,
        )


class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        # context: OrchestrationContext,
    ) -> states.State:
        self.context.proposed_state.state_details.flow_run_id = self.context.flow_run_id
        self.context.proposed_state.state_details.task_run_id = self.context.task_run_id
