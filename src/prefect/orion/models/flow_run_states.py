import contextlib
import sqlalchemy as sa
from sqlalchemy import select, delete
from typing import List
from uuid import UUID

from prefect.orion import schemas, models
from prefect.orion.models import orm
from prefect.orion.orchestration import global_policy
from prefect.orion.orchestration.rules import OrchestrationContext


async def create_flow_run_state(
    session: sa.orm.Session,
    flow_run_id: UUID,
    state: schemas.states.State,
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
    intended_transition = (initial_state.type if initial_state else None), state.type

    global_rules = global_policy.lookup_transition_rules(*intended_transition)

    context = OrchestrationContext(
        initial_state=initial_state,
        proposed_state=state,
        session=session,
        run=run,
        flow_run_id=flow_run_id,
    )

    # apply orchestration rules and create the new flow run state
    async with contextlib.AsyncExitStack() as stack:
        for rule in global_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        validated_state = orm.FlowRunState(
            flow_run_id=flow_run_id,
            **state.dict(shallow=True),
        )
        session.add(validated_state)
        await session.flush()

    # update the ORM model state
    if run is not None:
        run.state = validated_state
    return validated_state


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
        .filter(orm.FlowRunState.flow_run_id == flow_run_id)
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
