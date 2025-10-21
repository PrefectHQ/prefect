"""
Orchestration rules related to instrumenting the orchestration engine for Prefect
Observability
"""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import orm_models
from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.models.events import (
    TRUNCATE_STATE_MESSAGES_AT,
    flow_run_state_change_event,
    truncated_to,
)
from prefect.server.orchestration.rules import (
    FlowOrchestrationContext,
    FlowRunUniversalTransform,
    TaskOrchestrationContext,
    TaskRunUniversalTransform,
    OrchestrationContext,
)
from prefect.server.schemas import core


logger = logging.getLogger(__name__)


class TaskRunStateTransitionLogger(TaskRunUniversalTransform):
    """Log all task run state transitions for debugging purposes"""

    async def before_transition(self, context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy]) -> None:
        if not isinstance(context, TaskOrchestrationContext):
            return
            
        task_run = context.run
        initial_state = context.initial_state
        proposed_state = context.proposed_state
        initial_type = initial_state.type if initial_state else "None"
        proposed_type = proposed_state.type if proposed_state else "None"
        
        logger.debug(
            f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} (name='{task_run.name}') state transition requested: "
            f"{initial_type} -> {proposed_type}"
        )
        
        if initial_state:
            logger.debug(
                f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} initial state details: "
                f"name='{initial_state.name}', message='{initial_state.message or 'None'}'"
            )
        
        if proposed_state:
            logger.debug(
                f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} proposed state details: "
                f"name='{proposed_state.name}', message='{proposed_state.message or 'None'}'"
            )

    async def after_transition(self, context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy]) -> None:
        if not isinstance(context, TaskOrchestrationContext):
            return
            
        task_run = context.run
        initial_state = context.initial_state
        validated_state = context.validated_state
        initial_type = initial_state.type if initial_state else "None"
        validated_type = validated_state.type if validated_state else "None"
        
        logger.debug(
            f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} (name='{task_run.name}') state transition completed: "
            f"{initial_type} -> {validated_type}"
        )
        
        if validated_state:
            logger.debug(
                f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} validated state details: "
                f"name='{validated_state.name}', message='{validated_state.message or 'None'}'"
            )
        
        # Log orchestration context details if available
        if hasattr(context, 'response_status') and context.response_status:
            logger.debug(
                f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} orchestration status: {context.response_status}"
            )
        
        if hasattr(context, 'response_details') and context.response_details:
            logger.debug(
                f"STLOGGING: Task run {task_run.id}, flow_run_id {task_run.flow_run_id} orchestration details: {context.response_details}"
            )


class FlowRunStateTransitionLogger(FlowRunUniversalTransform):
    """Log all flow run state transitions for debugging purposes"""

    async def before_transition(self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]) -> None:
        if not isinstance(context, FlowOrchestrationContext):
            return
            
        flow_run = context.run
        initial_state = context.initial_state
        proposed_state = context.proposed_state
        initial_type = initial_state.type if initial_state else "None"
        proposed_type = proposed_state.type if proposed_state else "None"
        
        logger.debug(
            f"STLOGGING: Flow run {flow_run.id} (name='{flow_run.name}') state transition requested: "
            f"{initial_type} -> {proposed_type}"
        )
        
        if initial_state:
            logger.debug(
                f"STLOGGING: Flow run {flow_run.id} initial state details: "
                f"name='{initial_state.name}', message='{initial_state.message or 'None'}'"
            )
        
        if proposed_state:
            logger.debug(
                f"STLOGGING: Flow run {flow_run.id} proposed state details: "
                f"name='{proposed_state.name}', message='{proposed_state.message or 'None'}'"
            )

    async def after_transition(self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]) -> None:
        if not isinstance(context, FlowOrchestrationContext):
            return
            
        flow_run = context.run
        initial_state = context.initial_state
        validated_state = context.validated_state
        initial_type = initial_state.type if initial_state else "None"
        validated_type = validated_state.type if validated_state else "None"
        
        logger.debug(
            f"STLOGGING: Flow run {flow_run.id} (name='{flow_run.name}') state transition completed: "
            f"{initial_type} -> {validated_type}"
        )
        
        if validated_state:
            logger.debug(
                f"STLOGGING: Flow run {flow_run.id} validated state details: "
                f"name='{validated_state.name}', message='{validated_state.message or 'None'}'"
            )
        
        # Log orchestration context details if available
        if hasattr(context, 'response_status') and context.response_status:
            logger.debug(
                f"STLOGGING: Flow run {flow_run.id} orchestration status: {context.response_status}"
            )
        
        if hasattr(context, 'response_details') and context.response_details:
            logger.debug(
                f"STLOGGING: Flow run {flow_run.id} orchestration details: {context.response_details}"
            )


class InstrumentFlowRunStateTransitions(FlowRunUniversalTransform):
    """When a Flow Run changes states, fire a Prefect Event for the state change"""

    async def after_transition(
        self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]
    ) -> None:
        if not context.proposed_state or not context.validated_state:
            return

        if not isinstance(context, FlowOrchestrationContext):
            return

        initial_state = (
            context.initial_state.model_copy() if context.initial_state else None
        )
        validated_state = context.validated_state.model_copy()

        # Guard against passing large state payloads to arq
        if initial_state and context.initial_state:
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

        logger.debug(
            f"STLOGGING: INSTRUMENTATION POLICY: Emitting flow run state change event: "
            f"flow_run_id={context.run.id}, flow_run_name='{context.run.name}', "
            f"state_transition: {initial_state.type if initial_state else 'None'} -> {validated_state.type}, "
            f"validated_state_name='{validated_state.name}', occurred={validated_state.timestamp}"
        )

        async with PrefectServerEventsClient() as events:
            event = await flow_run_state_change_event(
                session=context.session,
                occurred=validated_state.timestamp,
                flow_run=context.run,
                initial_state_id=initial_state.id if initial_state else None,
                initial_state=initial_state,
                validated_state_id=validated_state.id,
                validated_state=validated_state,
            )
            
            logger.debug(
                f"STLOGGING: INSTRUMENTATION POLICY: Flow run event created: "
                f"event_type='{event.event}', event_id={event.id}, flow_run_id={context.run.flow_id}"
                f"resource_id='{event.resource.get('prefect.resource.id', 'unknown')}'"
            )
            
            await events.emit(event)
