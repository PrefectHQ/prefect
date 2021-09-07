from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import models, schemas
from prefect.orion.models import orm


async def create_flow_run(
    session: sa.orm.Session, flow_run: schemas.core.FlowRun
) -> orm.FlowRun:
    """Creates a new flow run. If the provided flow run has a state attached, it
    will also be created.

    Args:
        session (sa.orm.Session): a database session
        flow_run (schemas.core.FlowRun): a flow run model

    Returns:
        orm.FlowRun: the newly-created flow run
    """
    model = orm.FlowRun(**flow_run.dict(shallow=True, exclude={"state"}), state=None)
    session.add(model)
    await session.flush()
    if flow_run.state:
        await models.flow_run_states.orchestrate_flow_run_state(
            session=session, flow_run_id=model.id, state=flow_run.state
        )
    return model


async def read_flow_run(session: sa.orm.Session, flow_run_id: UUID) -> orm.FlowRun:
    """Reads a flow run by id

    Args:
        session (sa.orm.Session): A database session
        flow_run_id (str): a flow run id

    Returns:
        orm.FlowRun: the flow run
    """
    return await session.get(orm.FlowRun, flow_run_id)


async def read_flow_runs(
    session: sa.orm.Session,
    flow_id: UUID = None,
    offset: int = 0,
    limit: int = 10,
) -> List[orm.FlowRun]:
    """Read flow runs

    Args:
        session (sa.orm.Session): A database session
        flow_id (UUID): a flow_id
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm.FlowRun]: flow runs
    """
    filter_by = {}
    if flow_id:
        filter_by["flow_id"] = flow_id
    query = (
        select(orm.FlowRun)
        .filter_by(**filter_by)
        .offset(offset)
        .limit(limit)
        .order_by(orm.FlowRun.id)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_flow_run(session: sa.orm.Session, flow_run_id: UUID) -> bool:
    """Delete a flow run by flow_run_id

    Args:
        session (sa.orm.Session): A database session
        flow_run_id (str): a flow run id

    Returns:
        bool: whether or not the flow run was deleted
    """
    result = await session.execute(
        delete(orm.FlowRun).where(orm.FlowRun.id == flow_run_id)
    )
    return result.rowcount > 0
