"""
Functions for interacting with flow ORM objects.
Intended for internal use by the Orion API.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import dialect_specific_insert
from prefect.orion.models.dependencies import get_database_configuration


async def create_flow(
    session: sa.orm.Session,
    flow: schemas.core.Flow,
    get_db_config=get_database_configuration,
):
    """
    Creates a new flow.

    If a flow with the same name already exists, the existing flow is returned.

    Args:
        session: a database session
        flow: a flow model

    Returns:
        db_config.Flow: the newly-created or existing flow
    """
    db_config = await get_db_config()

    insert_stmt = (
        dialect_specific_insert(db_config.Flow)
        .values(**flow.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_nothing(
            index_elements=["name"],
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(db_config.Flow)
        .where(
            db_config.Flow.name == flow.name,
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()
    return model


async def update_flow(
    session: sa.orm.Session,
    flow_id: UUID,
    flow: schemas.actions.FlowUpdate,
    get_db_config=get_database_configuration,
):
    """
    Updates a flow.

    Args:
        session: a database session
        flow_id: the flow id to update
        flow: a flow update model

    Returns:
        bool: whether or not matching rows were found to update
    """
    db_config = await get_db_config()

    if not isinstance(flow, schemas.actions.FlowUpdate):
        raise ValueError(
            f"Expected parameter flow to have type schemas.actions.FlowUpdate, got {type(flow)!r} instead"
        )

    update_stmt = (
        sa.update(db_config.Flow).where(db_config.Flow.id == flow_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


async def read_flow(
    session: sa.orm.Session, flow_id: UUID, get_db_config=get_database_configuration
):
    """
    Reads a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        db_config.Flow: the flow
    """
    db_config = await get_db_config()
    return await session.get(db_config.Flow, flow_id)


async def read_flow_by_name(
    session: sa.orm.Session, name: str, get_db_config=get_database_configuration
):
    """
    Reads a flow by name.

    Args:
        session: A database session
        name: a flow name

    Returns:
        db_config.Flow: the flow
    """
    db_config = await get_db_config()

    result = await session.execute(select(db_config.Flow).filter_by(name=name))
    return result.scalar()


async def _apply_flow_filters(
    query,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    get_db_config=get_database_configuration,
):
    """
    Applies filters to a flow query as a combination of EXISTS subqueries.
    """
    db_config = await get_db_config()

    if flow_filter:
        query = query.where(flow_filter.as_sql_filter())

    if deployment_filter:
        exists_clause = select(orm.Deployment).where(
            orm.Deployment.flow_id == db_config.Flow.id,
            deployment_filter.as_sql_filter(),
        )
        query = query.where(exists_clause.exists())

    if flow_run_filter or task_run_filter:
        exists_clause = select(orm.FlowRun).where(
            orm.FlowRun.flow_id == db_config.Flow.id
        )

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter())

        if task_run_filter:
            exists_clause = exists_clause.join(
                orm.TaskRun,
                orm.TaskRun.flow_run_id == orm.FlowRun.id,
            ).where(task_run_filter.as_sql_filter())

        query = query.where(exists_clause.exists())

    return query


async def read_flows(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    offset: int = None,
    limit: int = None,
    get_db_config=get_database_configuration,
):
    """
    Read multiple flows.

    Args:
        session: A database session
        flow_filter: only select flows that match these filters
        flow_run_filter: only select flows whose flow runs match these filters
        task_run_filter: only select flows whose task runs match these filters
        deployment_filter: only select flows whose deployments match these filters
        offset: Query offset
        limit: Query limit

    Returns:
        List[db_config.Flow]: flows
    """
    db_config = await get_db_config()

    query = select(db_config.Flow).order_by(db_config.Flow.name)

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
    )

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
    deployment_filter: schemas.filters.DeploymentFilter = None,
    get_db_config=get_database_configuration,
) -> int:
    """
    Count flows.

    Args:
        session: A database session
        flow_filter: only count flows that match these filters
        flow_run_filter: only count flows whose flow runs match these filters
        task_run_filter: only count flows whose task runs match these filters
        deployment_filter: only count flows whose deployments match these filters

    Returns:
        int: count of flows
    """
    db_config = await get_db_config()

    query = select(sa.func.count(sa.text("*"))).select_from(db_config.Flow)

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
    )

    result = await session.execute(query)
    return result.scalar()


async def delete_flow(
    session: sa.orm.Session, flow_id: UUID, get_db_config=get_database_configuration
) -> bool:
    """
    Delete a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        bool: whether or not the flow was deleted
    """
    db_config = await get_db_config()

    result = await session.execute(
        delete(db_config.Flow).where(db_config.Flow.id == flow_id)
    )
    return result.rowcount > 0
