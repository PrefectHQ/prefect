from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import models, schemas
from prefect.orion.models import orm


async def create_task_run(
    session: sa.orm.Session, task_run: schemas.core.TaskRun
) -> orm.TaskRun:
    """Creates a new task run. If the provided task run has a state attached, it
    will also be created.

    Args:
        session (sa.orm.Session): a database session
        task_run (schemas.core.TaskRun): a task run model

    Returns:
        orm.TaskRun: the newly-created flow run
    """
    model = orm.TaskRun(**task_run.dict(shallow=True, exclude={"state"}), state=None)
    session.add(model)
    await session.flush()
    if task_run.state:
        await models.task_run_states.orchestrate_task_run_state(
            session=session, task_run_id=model.id, state=task_run.state
        )
    return model


async def read_task_run(session: sa.orm.Session, task_run_id: UUID) -> orm.TaskRun:
    """Read a task run by id

    Args:
        session (sa.orm.Session): a database session
        task_run_id (str): the task run id

    Returns:
        orm.TaskRun: the task run
    """
    model = await session.get(orm.TaskRun, task_run_id)
    return model


async def read_task_runs(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    offset: int = None,
    limit: int = None,
) -> List[orm.TaskRun]:
    """Read task runs

    Args:
        session (sa.orm.Session): a database session
        flow_filter (FlowFilter): only select task runs whose flows match these filters
        flow_run_filter (FlowRunFilter): only select task runs whose flow runs match these filters
        task_run_filter (TaskRunFilter): only select task runs that match these filters
        offset (int): Query offset
        limit (int): Query limit

    Returns:
        List[orm.TaskRun]: the task runs
    """
    query = select(orm.TaskRun).order_by(orm.TaskRun.id)

    if task_run_filter:
        query = query.where(task_run_filter.as_sql_filter())

    if flow_run_filter:
        query = query.join(
            orm.FlowRun, orm.FlowRun.id == orm.TaskRun.flow_run_id
        ).where(flow_run_filter.as_sql_filter())

    if flow_filter:
        if not flow_run_filter:
            query = query.join(orm.FlowRun, orm.FlowRun.id == orm.TaskRun.flow_run_id)

        query = query.join(orm.Flow, orm.Flow.id == orm.FlowRun.flow_id).where(
            flow_filter.as_sql_filter()
        )

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_task_runs(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
) -> int:
    """Count task runs

    Args:
        session (sa.orm.Session): a database session
        flow_filter (FlowFilter): only count task runs whose flows match these filters
        flow_run_filter (FlowRunFilter): only count task runs whose flow runs match these filters
        task_run_filter (TaskRunFilter): only count task runs that match these filters

    Returns:
        int: count of task runs
    """
    query = select(sa.func.count(sa.text("*"))).select_from(orm.TaskRun)

    if task_run_filter:
        query = query.where(task_run_filter.as_sql_filter())

    if flow_filter or flow_run_filter:
        exists_clause = select(orm.FlowRun).where(
            orm.FlowRun.id == orm.TaskRun.flow_run_id
        )

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter())

        if flow_filter:
            exists_clause = exists_clause.join(
                orm.Flow,
                orm.Flow.id == orm.FlowRun.flow_id,
            ).where(flow_filter.as_sql_filter())

        query = query.where(exists_clause.exists())

    result = await session.execute(query)
    return result.scalar()


async def delete_task_run(session: sa.orm.Session, task_run_id: UUID) -> bool:
    """Delete a task run by id

    Args:
        session (sa.orm.Session): a database session
        task_run_id (str): the task run id to delete

    Returns:
        bool: whether or not the task run was deleted
    """
    result = await session.execute(
        delete(orm.TaskRun).where(orm.TaskRun.id == task_run_id)
    )
    return result.rowcount > 0
