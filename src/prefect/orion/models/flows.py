"""
Functions for interacting with flow ORM objects.
Intended for internal use by the Orion API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_flow(
    session: sa.orm.Session, flow: schemas.core.Flow, db: OrionDBInterface
):
    """
    Creates a new flow.

    If a flow with the same name already exists, the existing flow is returned.

    Args:
        session: a database session
        flow: a flow model

    Returns:
        db.Flow: the newly-created or existing flow
    """

    insert_stmt = (
        (await db.insert(db.Flow))
        .values(**flow.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_nothing(
            index_elements=db.flow_unique_upsert_columns,
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.Flow)
        .where(
            db.Flow.name == flow.name,
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()
    return model


@inject_db
async def update_flow(
    session: sa.orm.Session,
    flow_id: UUID,
    flow: schemas.actions.FlowUpdate,
    db: OrionDBInterface,
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

    if not isinstance(flow, schemas.actions.FlowUpdate):
        raise ValueError(
            f"Expected parameter flow to have type schemas.actions.FlowUpdate, got {type(flow)!r} instead"
        )

    update_stmt = (
        sa.update(db.Flow).where(db.Flow.id == flow_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def read_flow(session: sa.orm.Session, flow_id: UUID, db: OrionDBInterface):
    """
    Reads a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        db.Flow: the flow
    """
    return await session.get(db.Flow, flow_id)


@inject_db
async def read_flow_by_name(session: sa.orm.Session, name: str, db: OrionDBInterface):
    """
    Reads a flow by name.

    Args:
        session: A database session
        name: a flow name

    Returns:
        db.Flow: the flow
    """

    result = await session.execute(select(db.Flow).filter_by(name=name))
    return result.scalar()


@inject_db
async def _apply_flow_filters(
    query,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
):
    """
    Applies filters to a flow query as a combination of EXISTS subqueries.
    """

    if flow_filter:
        query = query.where(flow_filter.as_sql_filter(db))

    if deployment_filter:
        exists_clause = select(db.Deployment).where(
            db.Deployment.flow_id == db.Flow.id,
            deployment_filter.as_sql_filter(db),
        )
        query = query.where(exists_clause.exists())

    if flow_run_filter or task_run_filter:
        exists_clause = select(db.FlowRun).where(db.FlowRun.flow_id == db.Flow.id)

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter(db))

        if task_run_filter:
            exists_clause = exists_clause.join(
                db.TaskRun,
                db.TaskRun.flow_run_id == db.FlowRun.id,
            ).where(task_run_filter.as_sql_filter(db))

        query = query.where(exists_clause.exists())

    return query


@inject_db
async def read_flows(
    session: sa.orm.Session,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    sort: schemas.sorting.FlowSort = schemas.sorting.FlowSort.NAME_ASC,
    offset: int = None,
    limit: int = None,
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
        List[db.Flow]: flows
    """

    query = select(db.Flow).order_by(sort.as_sql_sort(db=db))

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        db=db,
    )

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def count_flows(
    session: sa.orm.Session,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
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

    query = select(sa.func.count(sa.text("*"))).select_from(db.Flow)

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        db=db,
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def delete_flow(
    session: sa.orm.Session, flow_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        bool: whether or not the flow was deleted
    """

    result = await session.execute(delete(db.Flow).where(db.Flow.id == flow_id))
    return result.rowcount > 0
