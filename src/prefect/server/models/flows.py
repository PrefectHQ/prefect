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
from prefect.server.database import PrefectDBInterface, db_injector, orm_models

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
        db.queries.insert(db.Flow)
        .values(**flow.model_dump_for_orm(exclude_unset=True))
        .on_conflict_do_nothing(
            index_elements=db.orm.flow_unique_upsert_columns,
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.Flow)
        .where(db.Flow.name == flow.name)
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar_one()
    return model


@db_injector
async def update_flow(
    db: PrefectDBInterface,
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
        sa.update(db.Flow)
        .where(db.Flow.id == flow_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow.model_dump_for_orm(exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@db_injector
async def read_flow(
    db: PrefectDBInterface, session: AsyncSession, flow_id: UUID
) -> Optional[orm_models.Flow]:
    """
    Reads a flow by id.

    Args:
        session: A database session
        flow_id: a flow id

    Returns:
        orm_models.Flow: the flow
    """
    return await session.get(db.Flow, flow_id)


@db_injector
async def read_flow_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str
) -> Optional[orm_models.Flow]:
    """
    Reads a flow by name.

    Args:
        session: A database session
        name: a flow name

    Returns:
        orm_models.Flow: the flow
    """

    result = await session.execute(select(db.Flow).filter_by(name=name))
    return result.scalar()


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
        deployment_exists_clause = select(db.Deployment).where(
            db.Deployment.flow_id == db.Flow.id
        )

        if deployment_filter:
            deployment_exists_clause = deployment_exists_clause.where(
                deployment_filter.as_sql_filter(),
            )

        if work_pool_filter:
            deployment_exists_clause = deployment_exists_clause.join(
                db.WorkQueue,
                db.WorkQueue.id == db.Deployment.work_queue_id,
            )
            deployment_exists_clause = deployment_exists_clause.join(
                db.WorkPool,
                db.WorkPool.id == db.WorkQueue.work_pool_id,
            ).where(work_pool_filter.as_sql_filter())

        query = query.where(deployment_exists_clause.exists())

    if flow_run_filter or task_run_filter:
        flow_run_exists_clause = select(db.FlowRun).where(
            db.FlowRun.flow_id == db.Flow.id
        )

        if flow_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.where(
                flow_run_filter.as_sql_filter()
            )

        if task_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                db.TaskRun,
                db.TaskRun.flow_run_id == db.FlowRun.id,
            ).where(task_run_filter.as_sql_filter())

        query = query.where(flow_run_exists_clause.exists())

    return query


@db_injector
async def read_flows(
    db: PrefectDBInterface,
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

    query = select(db.Flow).order_by(*sort.as_sql_sort())

    query = await _apply_flow_filters(
        db,
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


@db_injector
async def count_flows(
    db: PrefectDBInterface,
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

    query = select(sa.func.count(None)).select_from(db.Flow)

    query = await _apply_flow_filters(
        db,
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


@db_injector
async def delete_flow(
    db: PrefectDBInterface, session: AsyncSession, flow_id: UUID
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


@db_injector
async def read_flow_labels(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_id: UUID,
) -> Union[schemas.core.KeyValueLabels, None]:
    result = await session.execute(select(db.Flow.labels).where(db.Flow.id == flow_id))

    return result.scalar()
