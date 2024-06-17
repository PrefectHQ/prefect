"""
Orchestration rules related to instrumenting the orchestration engine for Prefect
Observability
"""

from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.models.events import (
    TRUNCATE_STATE_MESSAGES_AT,
    flow_run_state_change_event,
    truncated_to,
)
from prefect.server.orchestration.rules import (
    BaseUniversalTransform,
    FlowOrchestrationContext,
    OrchestrationContext,
)


class InstrumentFlowRunStateTransitions(BaseUniversalTransform):
    """When a Flow Run changes states, fire a Prefect Event for the state change"""

    async def after_transition(self, context: OrchestrationContext) -> None:
        if not context.proposed_state or not context.validated_state:
            return

        if not isinstance(context, FlowOrchestrationContext):
            return

        initial_state = (
            context.initial_state.model_copy() if context.initial_state else None
        )
        validated_state = context.validated_state.model_copy()

        # Guard against passing large state payloads to arq
        if initial_state:
            initial_state.timestamp = context.initial_state.timestamp
            initial_state.message = truncated_to(
                TRUNCATE_STATE_MESSAGES_AT, initial_state.message
            )
        if validated_state:
            validated_state.timestamp = context.validated_state.timestamp
            validated_state.message = truncated_to(
                TRUNCATE_STATE_MESSAGES_AT, validated_state.message
            )

        assert isinstance(context.session, AsyncSession)

        async with PrefectServerEventsClient() as events:
            await events.emit(
                await flow_run_state_change_event(
                    session=context.session,
                    occurred=validated_state.timestamp,
                    flow_run=context.run,
                    initial_state_id=initial_state.id if initial_state else None,
                    initial_state=initial_state,
                    validated_state_id=validated_state.id,
                    validated_state=validated_state,
                )
            )
