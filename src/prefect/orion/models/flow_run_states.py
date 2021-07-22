from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm
from prefect.orion import schemas
from prefect.orion.schemas.core import RunDetails


async def create_flow_run_state(
    session: sa.orm.Session,
    flow_run_state: schemas.actions.StateCreate,
    flow_run_id: str,
) -> orm.FlowRunState:
    """Creates a new flow run state

    Args:
        session (sa.orm.Session): a database session
        flow_run_state (schemas.actions.FlowRunState): a flow run state model
        flow_run_id (str): the flow run id

    Returns:
        orm.FlowRunState: the newly-created flow run state
    """
    # carry over RunDetails from the most recent state
    most_recent_state = await read_most_recent_flow_run_state_by_flow_run_id(
        session=session, flow_run_id=flow_run_id
    )
    if most_recent_state is not None:
        run_details = most_recent_state.run_details
        run_details["previous_state_id"] = most_recent_state.id
    else:
        run_details = RunDetails().json_dict()

    # populate state details
    state_details = schemas.core.StateDetails(flow_run_id=flow_run_id).json_dict()

    # create the new flow run state
    new_flow_run_state = orm.FlowRunState(
        **flow_run_state.dict(exclude={"data"}),
        flow_run_id=flow_run_id,
        state_details=state_details,
        run_details=run_details
    )
    session.add(new_flow_run_state)
    await session.flush()
    return new_flow_run_state


async def read_flow_run_state(session: sa.orm.Session, id: str) -> orm.FlowRunState:
    """Reads a flow run state by id

    Args:
        session (sa.orm.Session): A database session
        id (str): a flow run state id

    Returns:
        orm.FlowRunState: the flow state
    """
    return await session.get(orm.FlowRunState, id)


async def read_flow_run_states(
    session: sa.orm.Session, flow_run_id: str
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
    return result.scalars().all()


async def read_most_recent_flow_run_state_by_flow_run_id(
    session: sa.orm.Session, flow_run_id: str
) -> orm.FlowRunState:
    """Reads the most recent state for a flow run

    Args:
        session (sa.orm.Session): A database session
        flow_run_id (str): the flow run id

    Returns:
        orm.FlowRunState: the most recent flow run state
    """
    query = (
        select(orm.FlowRunState)
        .filter(orm.FlowRunState.flow_run_id == flow_run_id)
        .order_by(orm.FlowRunState.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalars().first()


async def delete_flow_run_state(session: sa.orm.Session, id: str) -> bool:
    """Delete a flow run state by id

    Args:
        session (sa.orm.Session): A database session
        id (str): a flow run state id

    Returns:
        bool: whether or not the flow run state was deleted
    """
    result = await session.execute(
        delete(orm.FlowRunState).where(orm.FlowRunState.id == id)
    )
    return result.rowcount > 0
