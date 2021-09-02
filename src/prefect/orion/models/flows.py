from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect
from prefect.orion import schemas
from prefect.orion.models import orm


async def create_flow(session: sa.orm.Session, flow: schemas.core.Flow) -> orm.Flow:
    """Creates a new flow

    Args:
        session (sa.orm.Session): a database session
        flow (schemas.core.Flow): a flow model

    Returns:
        orm.Flow: the newly-created flow

    Raises:
        sqlalchemy.exc.IntegrityError: if a flow with the same name already exists

    """
    flow = orm.Flow(**flow.dict(shallow=True))
    session.add(flow)
    await session.flush()
    return flow


async def read_flow(session: sa.orm.Session, flow_id: UUID) -> orm.Flow:
    """Reads a flow by id

    Args:
        session (sa.orm.Session): A database session
        flow_id (str): a flow id

    Returns:
        orm.Flow: the flow
    """
    return await session.get(orm.Flow, flow_id)


async def read_flow_by_name(session: sa.orm.Session, name: str) -> orm.Flow:
    """Reads a flow by name

    Args:
        session (sa.orm.Session): A database session
        name (str): a flow name

    Returns:
        orm.Flow: the flow
    """
    stmt = await session.execute(select(orm.Flow).filter_by(name=name))
    return stmt.scalar()


async def read_flows(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    offset: int = None,
    limit: int = None,
) -> List[orm.Flow]:
    """Read flows

    Args:
        session (sa.orm.Session): A database session
        flow_filter (FlowFilter): only select flows that match these filters
        flow_run_filter (FlowFilter): only select flows whose flow runs match these filters
        task_run_filter (FlowFilter): only select flows whose task runs match these filters
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm.Flow]: flows
    """

    query = select(orm.Flow).order_by(orm.Flow.name)

    if flow_filter:
        query = query.filter(flow_filter.as_sql_filter())

    if flow_run_filter:
        query = query.join(
            orm.FlowRun,
            orm.Flow.id == orm.FlowRun.flow_id,
        ).filter(flow_run_filter.as_sql_filter())

    if task_run_filter:
        if not flow_run_filter:
            query = query.join(
                orm.FlowRun,
                orm.Flow.id == orm.FlowRun.flow_id,
            )

        query = query.join(
            orm.TaskRun,
            orm.FlowRun.id == orm.TaskRun.flow_run_id,
        ).filter(task_run_filter.as_sql_filter())

    if offset is not None:
        query = query.offset(offset)

    if limit is None:
        limit = prefect.settings.orion.database.default_limit

    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_flow(session: sa.orm.Session, flow_id: UUID) -> bool:
    """Delete a flow by id

    Args:
        session (sa.orm.Session): A database session
        flow_id (str): a flow id

    Returns:
        bool: whether or not the flow was deleted
    """
    result = await session.execute(delete(orm.Flow).where(orm.Flow.id == flow_id))
    return result.rowcount > 0
