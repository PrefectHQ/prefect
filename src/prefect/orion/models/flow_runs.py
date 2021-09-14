from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect
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


def _apply_flow_run_filters(
    query,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
):
    """
    Applies filters to a flow run query as a combination of correlated
    EXISTS subqueries.
    """

    if flow_run_filter:
        query = query.where(flow_run_filter.as_sql_filter())

    if flow_filter or task_run_filter:

        if flow_filter:
            exists_clause = select(orm.Flow).where(
                orm.Flow.id == orm.FlowRun.flow_id,
                flow_filter.as_sql_filter(),
            )

        if task_run_filter:
            if not flow_filter:
                exists_clause = select(orm.TaskRun).where(
                    orm.TaskRun.flow_run_id == orm.FlowRun.id
                )
            else:
                exists_clause = exists_clause.join(
                    orm.TaskRun, orm.TaskRun.flow_run_id == orm.FlowRun.id
                )
            exists_clause = exists_clause.where(
                orm.FlowRun.id == orm.TaskRun.flow_run_id,
                task_run_filter.as_sql_filter(),
            )

        query = query.where(exists_clause.exists())

    return query


async def read_flow_runs(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    offset: int = None,
    limit: int = None,
    sort=orm.FlowRun.id,
) -> List[orm.FlowRun]:
    """Read flow runs

    Args:
        session (sa.orm.Session): a database session
        flow_filter (FlowFilter): only select flow runs whose flows match these filters
        flow_run_filter (FlowRunFilter): only select flow runs match these filters
        task_run_filter (TaskRunFilter): only select flow runs whose task runs match these filters
        offset (int): Query offset
        limit (int): Query limit
        sort - TODO

    Returns:
        List[orm.FlowRun]: flow runs
    """
    query = select(orm.FlowRun).order_by(sort)

    query = _apply_flow_run_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
    )

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_flow_runs(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
) -> int:
    """Count flow runs

    Args:
        session (sa.orm.Session): a database session
        flow_filter (FlowFilter): only count flow runs whose flows match these filters
        flow_run_filter (FlowRunFilter): only count flow runs that match these filters
        task_run_filter (TaskRunFilter): only count flow runs whose task runs match these filters

    Returns:
        int: count of flow runs
    """
    query = select(sa.func.count(sa.text("*"))).select_from(orm.FlowRun)

    query = _apply_flow_run_filters(
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
    )

    result = await session.execute(query)
    return result.scalar()


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
