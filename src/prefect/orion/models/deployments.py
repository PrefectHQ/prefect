import datetime
from typing import List
from uuid import UUID, uuid4

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect
from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import dialect_specific_insert, get_dialect


async def create_deployment(
    session: sa.orm.Session,
    deployment: schemas.core.Deployment,
) -> orm.Deployment:
    """Upserts a deployment

    Args:
        session (sa.orm.Session): a database session
        deployment (schemas.core.Deployment): a deployment model

    Returns:
        orm.Deployment: the newly-created or updated deployment

    """
    insert_stmt = (
        dialect_specific_insert(orm.Deployment)
        .values(**deployment.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_update(
            index_elements=["flow_id", "name"],
            set_=deployment.dict(
                shallow=True,
                include={
                    "schedule",
                    "is_schedule_active",
                    "tags",
                    "parameters",
                    "flow_data",
                },
            ),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(orm.Deployment)
        .where(
            sa.and_(
                orm.Deployment.flow_id == deployment.flow_id,
                orm.Deployment.name == deployment.name,
            )
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()

    return model


async def read_deployment(
    session: sa.orm.Session, deployment_id: UUID
) -> orm.Deployment:
    """Reads a deployment by id

    Args:
        session (sa.orm.Session): A database session
        deployment_id (str): a deployment id

    Returns:
        orm.Deployment: the deployment
    """
    return await session.get(orm.Deployment, deployment_id)


async def read_deployment_by_name(
    session: sa.orm.Session, name: str, flow_name: str
) -> orm.Deployment:
    """Reads a deployment by name

    Args:
        session (sa.orm.Session): A database session
        name (str): a deployment name
        flow_name (str): the name of the flow the deployment belongs to

    Returns:
        orm.Deployment: the deployment
    """
    result = await session.execute(
        select(orm.Deployment)
        .join(orm.Flow, orm.Deployment.flow_id == orm.Flow.id)
        .where(sa.and_(orm.Flow.name == flow_name, orm.Deployment.name == name))
        .limit(1)
    )
    return result.scalar()


def _apply_deployment_filters(
    query,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
):
    """
    Applies filters to a deployment query as a combination of correlated
    EXISTS subqueries.
    """

    if deployment_filter:
        query = query.where(deployment_filter.as_sql_filter())

    if flow_filter:
        exists_clause = select(orm.Deployment.id).where(
            orm.Deployment.flow_id == orm.Flow.id, flow_filter.as_sql_filter()
        )

        query = query.where(exists_clause.exists())

    if flow_run_filter or task_run_filter:
        exists_clause = select(orm.FlowRun).where(
            orm.Deployment.id == orm.FlowRun.deployment_id
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


async def read_deployments(
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
) -> List[orm.Deployment]:
    """Read deployments

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit
        flow_filter (FlowFilter): only select deployments whose flows match these criteria
        flow_run_filter (FlowRunFilter): only select deployments whose flow runs match these criteria
        task_run_filter (TaskRunFilter): only select deployments whose task runs match these criteria
        deployment_filter (DeploymentFilter): only select deployment that match these filters


    Returns:
        List[orm.Deployment]: deployments
    """

    query = select(orm.Deployment).order_by(orm.Deployment.name)

    query = _apply_deployment_filters(
        query=query,
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


async def count_deployments(
    session: sa.orm.Session,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
) -> int:
    """Count deployments

    Args:
        session (sa.orm.Session): A database session
        flow_filter (FlowFilter): only count deployments whose flows match these criteria
        flow_run_filter (FlowRunFilter): only count deployments whose flow runs match these criteria
        task_run_filter (TaskRunFilter): only count deployments whose task runs match these criteria
        deployment_filter (DeploymentFilter): only count deployment that match these filters

    Returns:
        int: the number of deployments matching filters
    """

    query = select(sa.func.count(sa.text("*"))).select_from(orm.Deployment)

    query = _apply_deployment_filters(
        query=query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
    )

    result = await session.execute(query)
    return result.scalar()


async def delete_deployment(session: sa.orm.Session, deployment_id: UUID) -> bool:
    """Delete a deployment by id

    Args:
        session (sa.orm.Session): A database session
        deployment_id (str): a deployment id

    Returns:
        bool: whether or not the deployment was deleted
    """
    result = await session.execute(
        delete(orm.Deployment).where(orm.Deployment.id == deployment_id)
    )
    return result.rowcount > 0


async def schedule_runs(
    session: sa.orm.Session,
    deployment_id: UUID,
    start_time: datetime.datetime = None,
    end_time: datetime.datetime = None,
    max_runs: int = None,
):
    if max_runs is None:
        max_runs = prefect.settings.orion.services.scheduler_max_runs
    if start_time is None:
        start_time = pendulum.now("UTC")
    start_time = pendulum.instance(start_time)
    if end_time is None:
        end_time = start_time + (
            prefect.settings.orion.services.scheduler_max_scheduled_time
        )
    end_time = pendulum.instance(end_time)

    runs = await _generate_scheduled_flow_runs(
        session=session,
        deployment_id=deployment_id,
        start_time=start_time,
        end_time=end_time,
        max_runs=max_runs,
    )
    return await _insert_scheduled_flow_runs(session=session, runs=runs)


async def _generate_scheduled_flow_runs(
    session: sa.orm.Session,
    deployment_id: UUID,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    max_runs: int,
) -> List[schemas.core.FlowRun]:
    """
    Given a `deployment_id` and schedule, generates a list of flow run objects and
    associated scheduled states that represent scheduled flow runs. This method
    does NOT insert generated runs into the database, in order to facilitate
    batch operations. Call `_insert_scheduled_flow_runs()` to insert these runs.
    """
    runs = []

    # retrieve the deployment
    deployment = await session.get(orm.Deployment, deployment_id)

    if not deployment or not deployment.schedule or not deployment.is_schedule_active:
        return []

    dates = await deployment.schedule.get_dates(
        n=max_runs, start=start_time, end=end_time
    )

    for date in dates:
        run = schemas.core.FlowRun(
            flow_id=deployment.flow_id,
            deployment_id=deployment_id,
            parameters=deployment.parameters,
            idempotency_key=f"scheduled {deployment.id} {date}",
            tags=["auto-scheduled"] + deployment.tags,
            auto_scheduled=True,
            state=schemas.states.Scheduled(
                scheduled_time=date,
                message="Flow run scheduled",
            ),
            state_type=schemas.states.StateType.SCHEDULED,
            next_scheduled_start_time=date,
            expected_start_time=date,
        )
        runs.append(run)

    return runs


async def _insert_scheduled_flow_runs(
    session: sa.orm.Session,
    runs: List[schemas.core.FlowRun],
) -> List[schemas.core.FlowRun]:
    """
    Given a list of flow runs to schedule, as generated by `_generate_scheduled_flow_runs`,
    inserts them into the database. Note this is a separate method to facilitate batch
    operations on many scheduled runs.

    Returns a list of flow runs that were created
    """

    if not runs:
        return []

    # gracefully insert the flow runs against the idempotency key
    # this syntax (insert statement, values to insert) is most efficient
    # because it uses a single bind parameter
    insert = dialect_specific_insert(orm.FlowRun)
    await session.execute(
        insert.on_conflict_do_nothing(index_elements=["flow_id", "idempotency_key"]),
        [r.dict(exclude={"created", "updated"}) for r in runs],
    )

    # query for the rows that were newly inserted (by checking for any flow runs with
    # no corresponding flow run states)
    inserted_rows = (
        sa.select(orm.FlowRun.id)
        .join(
            orm.FlowRunState,
            orm.FlowRun.id == orm.FlowRunState.flow_run_id,
            isouter=True,
        )
        .where(
            orm.FlowRun.id.in_([r.id for r in runs]),
            orm.FlowRunState.id.is_(None),
        )
    )
    inserted_flow_run_ids = (await session.execute(inserted_rows)).scalars().all()

    # insert flow run states that correspond to the newly-insert rows
    insert_flow_run_states = [
        {"id": uuid4(), "flow_run_id": r.id, **r.state.dict()}
        for r in runs
        if r.id in inserted_flow_run_ids
    ]
    if insert_flow_run_states:
        # this syntax (insert statement, values to insert) is most efficient
        # because it uses a single bind parameter
        await session.execute(
            orm.FlowRunState.__table__.insert(), insert_flow_run_states
        )

        # set the `state_id` on the newly inserted runs
        if get_dialect().name == "postgresql":
            # postgres supports `UPDATE ... FROM` syntax
            stmt = (
                sa.update(orm.FlowRun)
                .where(
                    orm.FlowRun.id.in_(inserted_flow_run_ids),
                    orm.FlowRunState.flow_run_id == orm.FlowRun.id,
                    orm.FlowRunState.id.in_([r["id"] for r in insert_flow_run_states]),
                )
                .values(state_id=orm.FlowRunState.id)
                # no need to synchronize as these flow runs are entirely new
                .execution_options(synchronize_session=False)
            )
        else:
            # sqlite requires a correlated subquery to update from another table
            subquery = (
                sa.select(orm.FlowRunState.id)
                .where(
                    orm.FlowRunState.flow_run_id == orm.FlowRun.id,
                    orm.FlowRunState.id.in_([r["id"] for r in insert_flow_run_states]),
                )
                .limit(1)
                .scalar_subquery()
            )
            stmt = (
                sa.update(orm.FlowRun)
                .where(
                    orm.FlowRun.id.in_(inserted_flow_run_ids),
                )
                .values(state_id=subquery)
                # no need to synchronize as these flow runs are entirely new
                .execution_options(synchronize_session=False)
            )

        await session.execute(stmt)

    return [r for r in runs if r.id in inserted_flow_run_ids]
