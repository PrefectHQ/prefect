from typing import List
from uuid import UUID
import pendulum

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import dialect_specific_insert


async def create_flow(session: sa.orm.Session, flow: schemas.core.Flow) -> orm.Flow:
    """Creates a new flow. If a flow with the same name already exists, the existing flow is returned.

    Args:
        session (sa.orm.Session): a database session
        flow (schemas.core.Flow): a flow model

    Returns:
        orm.Flow: the newly-created or existing flow
    """
    insert_stmt = (
        dialect_specific_insert(orm.Flow)
        .values(**flow.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_nothing(
            index_elements=["name"],
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(orm.Flow)
        .where(
            orm.Flow.name == flow.name,
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()
    return model


async def update_flow(
    session: sa.orm.Session, flow_id: UUID, flow: schemas.core.Flow
) -> orm.Flow:
    """
    Updates a flow

    Args:
        session (sa.orm.Session): a database session
        flow_id (UUID): the flow id to update
        flow (schemas.core.Flow): a flow model

    Returns:
        orm.Flow: the updated flow

    """
    update_stmt = (
        sa.update(orm.Flow).where(orm.Flow.id == flow_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow.dict(shallow=True, exclude_unset=True))
    )
    await session.execute(update_stmt)
    model = await read_flow(session=session, flow_id=flow_id)
    return model


async def read_flow(session: sa.orm.Session, flow_id: UUID) -> orm.Flow:
    """Reads a flow by id

    Args:
        session (sa.orm.Session): A database session
        flow_id (UUID): a flow id

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
        flow_run_filter (FlowRunFilter): only select flows whose flow runs match these filters
        task_run_filter (TaskRunFilter): only select flows whose task runs match these filters
        offset (int): Query offset
        limit (int): Query limit

    Returns:
        List[orm.Flow]: flows
    """

    query = select(orm.Flow).order_by(orm.Flow.name)

    if flow_filter:
        query = query.where(flow_filter.as_sql_filter())

    if flow_run_filter:
        query = query.join(
            orm.FlowRun,
            orm.Flow.id == orm.FlowRun.flow_id,
        ).where(flow_run_filter.as_sql_filter())

    if task_run_filter:
        if not flow_run_filter:
            query = query.join(
                orm.FlowRun,
                orm.Flow.id == orm.FlowRun.flow_id,
            )

        query = query.join(
            orm.TaskRun,
            orm.FlowRun.id == orm.TaskRun.flow_run_id,
        ).where(task_run_filter.as_sql_filter())

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_flows(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
) -> int:
    """Count flows

    Args:
        session (sa.orm.Session): A database session
        flow_filter (FlowFilter): only count flows that match these filters
        flow_run_filter (FlowRunFilter): only count flows whose flow runs match these filters
        task_run_filter (TaskRunFilter): only count flows whose task runs match these filters

    Returns:
        int: count of flows
    """

    query = select(sa.func.count(sa.text("*"))).select_from(orm.Flow)

    if flow_filter:
        query = query.where(flow_filter.as_sql_filter())

    if flow_run_filter or task_run_filter:
        exists_clause = select(orm.FlowRun).where(orm.FlowRun.flow_id == orm.Flow.id)

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter())

        if task_run_filter:
            exists_clause = exists_clause.join(
                orm.TaskRun,
                orm.TaskRun.flow_run_id == orm.FlowRun.id,
            ).where(task_run_filter.as_sql_filter())

        query = query.where(exists_clause.exists())

    result = await session.execute(query)
    return result.scalar()


async def delete_flow(session: sa.orm.Session, flow_id: UUID) -> bool:
    """Delete a flow by id

    Args:
        session (sa.orm.Session): A database session
        flow_id (UUID): a flow id

    Returns:
        bool: whether or not the flow was deleted
    """
    result = await session.execute(delete(orm.Flow).where(orm.Flow.id == flow_id))
    return result.rowcount > 0
