"""
Functions for interacting with flow ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Optional, Sequence, TypeVar, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

import prefect.server.schemas as schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface

T = TypeVar("T", bound=tuple)


@db_injector
async def create_flow(
    db: PrefectDBInterface, session: AsyncSession, flow: schemas.core.Flow
) -> orm_models.Flow:
    """
    Creates a new flow.

    If a flow with the same name already exists, the existing flow is returned.

    Args:
        session: a database session
        flow: a flow model

    Returns:
        orm_models.Flow: the newly-created or existing flow
    """

    insert_stmt = (
        db.insert(orm_models.Flow)
        .values(**flow.model_dump_for_orm(exclude_unset=True))
        .on_conflict_do_nothing(
            index_elements=db.flow_unique_upsert_columns,
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(orm_models.Flow)
        .where(
            orm_models.Flow.name == flow.name,
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar_one()
    return model


async def update_flow(
    session: AsyncSession,
    flow_id: UUID,
    flow: schemas.actions.FlowUpdate,
) -> bool:
    """
    Updates a flow.

    Args:
        session: a database session
        flow_id: the flow id to update
        flow: a flow update model

    Returns:
        bool: whether or not matching rows were found to update
    """
    update_stmt = (
        sa.update(orm_models.Flow)
        .where(orm_models.Flow.id == flow_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow.model_dump_for_orm(exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


async def read_flow(session: AsyncSession, flow_id: UUID) -> Optional[orm_models.Flow]:
    """
    Reads a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        orm_models.Flow: the flow
    """
    return await session.get(orm_models.Flow, flow_id)


async def read_flow_by_name(
    session: AsyncSession, name: str
) -> Optional[orm_models.Flow]:
    """
    Reads a flow by name.

    Args:
        session: A database session
        name: a flow name

    Returns:
        orm_models.Flow: the flow
    """

    result = await session.execute(select(orm_models.Flow).filter_by(name=name))
    return result.scalar()


@db_injector
async def _apply_flow_filters(
    db: PrefectDBInterface,
    query: Select[T],
    flow_filter: Union[schemas.filters.FlowFilter, None] = None,
    flow_run_filter: Union[schemas.filters.FlowRunFilter, None] = None,
    task_run_filter: Union[schemas.filters.TaskRunFilter, None] = None,
    deployment_filter: Union[schemas.filters.DeploymentFilter, None] = None,
    work_pool_filter: Union[schemas.filters.WorkPoolFilter, None] = None,
) -> Select[T]:
    """
    Applies filters to a flow query as a combination of EXISTS subqueries.
    """

    if flow_filter:
        query = query.where(flow_filter.as_sql_filter())

    if deployment_filter or work_pool_filter:
        deployment_exists_clause = select(orm_models.Deployment).where(
            orm_models.Deployment.flow_id == orm_models.Flow.id
        )

        if deployment_filter:
            deployment_exists_clause = deployment_exists_clause.where(
                deployment_filter.as_sql_filter(),
            )

        if work_pool_filter:
            deployment_exists_clause = deployment_exists_clause.join(
                orm_models.WorkQueue,
                orm_models.WorkQueue.id == orm_models.Deployment.work_queue_id,
            )
            deployment_exists_clause = deployment_exists_clause.join(
                orm_models.WorkPool,
                orm_models.WorkPool.id == orm_models.WorkQueue.work_pool_id,
            ).where(work_pool_filter.as_sql_filter())

        query = query.where(deployment_exists_clause.exists())

    if flow_run_filter or task_run_filter:
        flow_run_exists_clause = select(orm_models.FlowRun).where(
            orm_models.FlowRun.flow_id == orm_models.Flow.id
        )

        if flow_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.where(
                flow_run_filter.as_sql_filter()
            )

        if task_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                orm_models.TaskRun,
                orm_models.TaskRun.flow_run_id == orm_models.FlowRun.id,
            ).where(task_run_filter.as_sql_filter())

        query = query.where(flow_run_exists_clause.exists())

    return query


async def read_flows(
    session: AsyncSession,
    flow_filter: Union[schemas.filters.FlowFilter, None] = None,
    flow_run_filter: Union[schemas.filters.FlowRunFilter, None] = None,
    task_run_filter: Union[schemas.filters.TaskRunFilter, None] = None,
    deployment_filter: Union[schemas.filters.DeploymentFilter, None] = None,
    work_pool_filter: Union[schemas.filters.WorkPoolFilter, None] = None,
    sort: schemas.sorting.FlowSort = schemas.sorting.FlowSort.NAME_ASC,
    offset: Union[int, None] = None,
    limit: Union[int, None] = None,
) -> Sequence[orm_models.Flow]:
    """
    Read multiple flows.

    Args:
        session: A database session
        flow_filter: only select flows that match these filters
        flow_run_filter: only select flows whose flow runs match these filters
        task_run_filter: only select flows whose task runs match these filters
        deployment_filter: only select flows whose deployments match these filters
        work_pool_filter: only select flows whose work pools match these filters
        offset: Query offset
        limit: Query limit

    Returns:
        List[orm_models.Flow]: flows
    """

    query = select(orm_models.Flow).order_by(sort.as_sql_sort())

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
    )

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_flows(
    session: AsyncSession,
    flow_filter: Union[schemas.filters.FlowFilter, None] = None,
    flow_run_filter: Union[schemas.filters.FlowRunFilter, None] = None,
    task_run_filter: Union[schemas.filters.TaskRunFilter, None] = None,
    deployment_filter: Union[schemas.filters.DeploymentFilter, None] = None,
    work_pool_filter: Union[schemas.filters.WorkPoolFilter, None] = None,
) -> int:
    """
    Count flows.

    Args:
        session: A database session
        flow_filter: only count flows that match these filters
        flow_run_filter: only count flows whose flow runs match these filters
        task_run_filter: only count flows whose task runs match these filters
        deployment_filter: only count flows whose deployments match these filters
        work_pool_filter: only count flows whose work pools match these filters

    Returns:
        int: count of flows
    """

    query = select(sa.func.count(sa.text("*"))).select_from(orm_models.Flow)

    query = await _apply_flow_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


async def delete_flow(session: AsyncSession, flow_id: UUID) -> bool:
    """
    Delete a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        bool: whether or not the flow was deleted
    """

    result = await session.execute(
        delete(orm_models.Flow).where(orm_models.Flow.id == flow_id)
    )
    return result.rowcount > 0
