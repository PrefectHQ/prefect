from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm
from prefect.orion import schemas


async def create_flow_run(
    session: sa.orm.Session, flow_run: schemas.actions.FlowRunCreate
) -> orm.FlowRun:
    """Creates a new flow run

    Args:
        session (sa.orm.Session): a database session
        flow_run (schemas.core.FlowRun): a flow run model

    Returns:
        orm.FlowRun: the newly-created flow run
    """
    new_flow_run = orm.FlowRun(**flow_run.dict())
    session.add(new_flow_run)
    await session.flush()
    return new_flow_run


async def read_flow_run(session: sa.orm.Session, id: str) -> orm.FlowRun:
    """Reads a flow run by id

    Args:
        session (sa.orm.Session): A database session
        id (str): a flow run id

    Returns:
        orm.FlowRun: the flow run
    """
    return await session.get(orm.FlowRun, id)


async def read_flow_runs(
    session: sa.orm.Session,
    offset: int = 0,
    limit: int = 10,
) -> List[orm.FlowRun]:
    """Read flow runs

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm.FlowRun]: flow runs
    """
    query = select(orm.FlowRun).offset(offset).limit(limit).order_by(orm.FlowRun.id)
    result = await session.execute(query)
    return result.scalars().all()


async def read_current_state(
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


async def delete_flow_run(session: sa.orm.Session, id: str) -> bool:
    """Delete a flow run by id

    Args:
        session (sa.orm.Session): A database session
        id (str): a flow run id

    Returns:
        bool: whether or not the flow run was deleted
    """
    result = await session.execute(delete(orm.FlowRun).where(orm.FlowRun.id == id))
    return result.rowcount > 0
