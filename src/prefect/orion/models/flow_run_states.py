import contextlib
from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import models, schemas
from prefect.orion.models import orm
from prefect.orion.orchestration.global_policy import GlobalPolicy
from prefect.orion.orchestration.core_policy import CoreFlowPolicy
from prefect.orion.orchestration.rules import (
    FlowOrchestrationContext,
    OrchestrationResult,
)


async def orchestrate_flow_run_state(
    session: sa.orm.Session,
    flow_run_id: UUID,
    state: schemas.states.State,
    apply_orchestration_rules: bool = True,
) -> orm.FlowRunState:
    """Creates a new flow run state

    Args:
        session (sa.orm.Session): a database session
        flow_run_id (str): the flow run id
        state (schemas.states.State): a flow run state model

    Returns:
        orm.FlowRunState: the newly-created flow run state
    """
    # load the flow run
    run = await models.flow_runs.read_flow_run(
        session=session,
        flow_run_id=flow_run_id,
    )

    if not run:
        raise ValueError(f"Invalid flow run: {flow_run_id}")

    initial_state = run.state.as_state() if run.state else None
    initial_state_type = initial_state.type if initial_state else None
    proposed_state_type = state.type if state else None
    intended_transition = (initial_state_type, proposed_state_type)

    global_rules = GlobalPolicy.compile_transition_rules(*intended_transition)

    if apply_orchestration_rules:
        orchestration_rules = CoreFlowPolicy.compile_transition_rules(
            *intended_transition
        )
    else:
        orchestration_rules = []

    context = FlowOrchestrationContext(
        initial_state=initial_state,
        proposed_state=state,
        session=session,
        run=run,
        run_id=flow_run_id,
    )

    # apply orchestration rules and create the new flow run state
    async with contextlib.AsyncExitStack() as stack:
        for rule in orchestration_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        for rule in global_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        validated_orm_state = await context.validate_proposed_state()

        if validated_orm_state is not None:
            run.set_state(validated_orm_state)
            await session.flush()

    result = OrchestrationResult(
        state=validated_orm_state,
        status=context.response_status,
        details=context.response_details,
    )

    return result


async def read_flow_run_state(
    session: sa.orm.Session, flow_run_state_id: UUID
) -> orm.FlowRunState:
    """Reads a flow run state by id

    Args:
        session (sa.orm.Session): A database session
        flow_run_state_id (str): a flow run state id

    Returns:
        orm.FlowRunState: the flow state
    """
    return await session.get(orm.FlowRunState, flow_run_state_id)


async def read_flow_run_states(
    session: sa.orm.Session, flow_run_id: UUID
) -> List[orm.FlowRunState]:
    """Reads flow runs states for a flow run

    Args:
        session (sa.orm.Session): A database session
        flow_run_id (str): the flow run id

    Returns:
        List[orm.FlowRunState]: the flow run states
    """
    query = (
        select(orm.FlowRunState)
        .filter_by(flow_run_id=flow_run_id)
        .order_by(orm.FlowRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_flow_run_state(
    session: sa.orm.Session, flow_run_state_id: UUID
) -> bool:
    """Delete a flow run state by id

    Args:
        session (sa.orm.Session): A database session
        flow_run_state_id (str): a flow run state id

    Returns:
        bool: whether or not the flow run state was deleted
    """
    result = await session.execute(
        delete(orm.FlowRunState).where(orm.FlowRunState.id == flow_run_state_id)
    )
    return result.rowcount > 0
