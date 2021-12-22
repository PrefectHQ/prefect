"""
Functions for interacting with log ORM objects.
Intended for internal use by the Orion API.
"""
from uuid import UUID

import pendulum
import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def read_log(session: sa.orm.Session, task_run_id: UUID, db: OrionDBInterface):
    """
    Read a log by ID.

    Args:
        session: a database session
        log_id: the log ID

    Returns:
        db.Log: the log
    """

    model = await session.get(db.TaskRun, task_run_id)
    return model


@inject_db
async def create_log(
    session: sa.orm.Session, db: OrionDBInterface, log: schemas.core.Log
):
    """
    Creates a new log.

    Args:
        session: a database session
        log: a log schema

    Returns:
        db.Log: the newly-created or existing log
    """

    now = pendulum.now("UTC")

    # if a dynamic key exists, we need to guard against conflicts
    insert_stmt = (
        (await db.insert(db.Log))
        .values(**log.dict())
        .on_conflict_do_nothing(
            index_elements=db.task_run_unique_upsert_columns,
        )
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.TaskRun)
        .where(
            sa.and_(
                db.TaskRun.flow_run_id == task_run.flow_run_id,
                db.TaskRun.task_key == task_run.task_key,
                db.TaskRun.dynamic_key == task_run.dynamic_key,
            )
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()

    if model.created >= now and task_run.state:
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=model.id,
            state=task_run.state,
            force=True,
        )
    return model


@inject_db
async def _apply_task_run_filters(
    query,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
):
    """
    Applies filters to a task run query as a combination of EXISTS subqueries.
    """

    if task_run_filter:
        query = query.where(task_run_filter.as_sql_filter())

    if flow_filter or flow_run_filter or deployment_filter:
        exists_clause = select(db.FlowRun).where(
            db.FlowRun.id == db.TaskRun.flow_run_id
        )

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter())

        if flow_filter:
            exists_clause = exists_clause.join(
                db.Flow,
                db.Flow.id == db.FlowRun.flow_id,
            ).where(flow_filter.as_sql_filter())

        if deployment_filter:
            exists_clause = exists_clause.join(
                db.Deployment,
                db.Deployment.id == db.FlowRun.deployment_id,
            ).where(deployment_filter.as_sql_filter())

        query = query.where(exists_clause.exists())

    return query
