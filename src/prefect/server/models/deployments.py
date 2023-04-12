"""
Functions for interacting with deployment ORM objects.
Intended for internal use by the Prefect REST API.
"""

import datetime
from typing import Dict, List
from uuid import UUID, uuid4

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, or_, select

from prefect.server import models, schemas
from prefect.server.api.workers import WorkerLookups
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.utilities.database import json_contains
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME,
)


@inject_db
async def _delete_scheduled_runs(
    session: sa.orm.Session,
    deployment_id: UUID,
    db: PrefectDBInterface,
    auto_scheduled_only: bool = False,
):
    """
    This utility function deletes all of a deployment's scheduled runs that are
    still in a Scheduled state It should be run any time a deployment is created or
    modified in order to ensure that future runs comply with the deployment's latest values.

    Args:
        deployment_id: the deplyment for which we should delete runs.
        auto_scheduled_only: if True, only delete auto scheduled runs. Defaults to `False`.
    """
    delete_query = sa.delete(db.FlowRun).where(
        db.FlowRun.deployment_id == deployment_id,
        db.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
    )

    if auto_scheduled_only:
        delete_query = delete_query.where(
            db.FlowRun.auto_scheduled.is_(True),
        )

    await session.execute(delete_query)


@inject_db
async def create_deployment(
    session: sa.orm.Session, deployment: schemas.core.Deployment, db: PrefectDBInterface
):
    """Upserts a deployment.

    Args:
        session: a database session
        deployment: a deployment model

    Returns:
        db.Deployment: the newly-created or updated deployment

    """

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    deployment.updated = pendulum.now("UTC")

    insert_values = deployment.dict(shallow=True, exclude_unset=True)

    insert_stmt = (
        (await db.insert(db.Deployment))
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=db.deployment_unique_upsert_columns,
            set_={
                **deployment.dict(
                    shallow=True,
                    exclude_unset=True,
                    exclude={"id", "created", "created_by"},
                ),
            },
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(db.Deployment)
        .where(
            sa.and_(
                db.Deployment.flow_id == deployment.flow_id,
                db.Deployment.name == deployment.name,
            )
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()

    if model.work_queue_name:
        await models.work_queues._ensure_work_queue_exists(
            session=session, name=model.work_queue_name, db=db
        )

    # because this could upsert a different schedule, delete any runs from the old
    # deployment
    await _delete_scheduled_runs(
        session=session, deployment_id=model.id, db=db, auto_scheduled_only=True
    )

    return model


@inject_db
async def update_deployment(
    session: sa.orm.Session,
    deployment_id: UUID,
    deployment: schemas.actions.DeploymentUpdate,
    db: PrefectDBInterface,
) -> bool:
    """Updates a deployment.

    Args:
        session: a database session
        deployment_id: the ID of the deployment to modify
        deployment: changes to a deployment model

    Returns:
        bool: whether the deployment was updated

    """

    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = deployment.dict(
        shallow=True,
        exclude_unset=True,
        exclude={"work_pool_name"},
    )
    if deployment.work_pool_name and deployment.work_queue_name:
        # If a specific pool name/queue name combination was provided, get the
        # ID for that work pool queue.
        update_data[
            "work_queue_id"
        ] = await WorkerLookups()._get_work_queue_id_from_name(
            session=session,
            work_pool_name=deployment.work_pool_name,
            work_queue_name=deployment.work_queue_name,
            create_queue_if_not_found=True,
        )
    elif deployment.work_pool_name:
        # If just a pool name was provided, get the ID for its default
        # work pool queue.
        update_data[
            "work_queue_id"
        ] = await WorkerLookups()._get_default_work_queue_id_from_work_pool_name(
            session=session,
            work_pool_name=deployment.work_pool_name,
        )
    elif deployment.work_queue_name:
        # If just a queue name was provided, ensure the queue exists and
        # get its ID.
        work_queue = await models.work_queues._ensure_work_queue_exists(
            session=session, name=update_data["work_queue_name"], db=db
        )
        update_data["work_queue_id"] = work_queue.id

    update_stmt = (
        sa.update(db.Deployment)
        .where(db.Deployment.id == deployment_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)

    # delete any auto scheduled runs that would have reflected the old deployment config
    await _delete_scheduled_runs(
        session=session, deployment_id=deployment_id, db=db, auto_scheduled_only=True
    )

    # create work queue if it doesn't exist
    if update_data.get("work_queue_name"):
        await models.work_queues._ensure_work_queue_exists(
            session=session, name=update_data["work_queue_name"], db=db
        )

    return result.rowcount > 0


@inject_db
async def read_deployment(
    session: sa.orm.Session, deployment_id: UUID, db: PrefectDBInterface
):
    """Reads a deployment by id.

    Args:
        session: A database session
        deployment_id: a deployment id

    Returns:
        db.Deployment: the deployment
    """

    return await session.get(db.Deployment, deployment_id)


@inject_db
async def read_deployment_by_name(
    session: sa.orm.Session, name: str, flow_name: str, db: PrefectDBInterface
):
    """Reads a deployment by name.

    Args:
        session: A database session
        name: a deployment name
        flow_name: the name of the flow the deployment belongs to

    Returns:
        db.Deployment: the deployment
    """

    result = await session.execute(
        select(db.Deployment)
        .join(db.Flow, db.Deployment.flow_id == db.Flow.id)
        .where(
            sa.and_(
                db.Flow.name == flow_name,
                db.Deployment.name == name,
            )
        )
        .limit(1)
    )
    return result.scalar()


@inject_db
async def _apply_deployment_filters(
    query,
    db: PrefectDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    work_pool_filter: schemas.filters.WorkPoolFilter = None,
    work_queue_filter: schemas.filters.WorkQueueFilter = None,
):
    """
    Applies filters to a deployment query as a combination of EXISTS subqueries.
    """

    if deployment_filter:
        query = query.where(deployment_filter.as_sql_filter(db))

    if flow_filter:
        exists_clause = select(db.Deployment.id).where(
            db.Deployment.flow_id == db.Flow.id,
            flow_filter.as_sql_filter(db),
        )

        query = query.where(exists_clause.exists())

    if flow_run_filter or task_run_filter:
        exists_clause = select(db.FlowRun).where(
            db.Deployment.id == db.FlowRun.deployment_id
        )

        if flow_run_filter:
            exists_clause = exists_clause.where(flow_run_filter.as_sql_filter(db))
        if task_run_filter:
            exists_clause = exists_clause.join(
                db.TaskRun,
                db.TaskRun.flow_run_id == db.FlowRun.id,
            ).where(task_run_filter.as_sql_filter(db))

        query = query.where(exists_clause.exists())

    if work_pool_filter or work_queue_filter:
        exists_clause = select(db.WorkQueue).where(
            db.Deployment.work_queue_id == db.WorkQueue.id
        )

        if work_queue_filter:
            exists_clause = exists_clause.where(work_queue_filter.as_sql_filter(db))

        if work_pool_filter:
            exists_clause = exists_clause.join(
                db.WorkPool, db.WorkPool.id == db.WorkQueue.work_pool_id
            ).where(work_pool_filter.as_sql_filter(db))

        query = query.where(exists_clause.exists())

    return query


@inject_db
async def read_deployments(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    offset: int = None,
    limit: int = None,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    work_pool_filter: schemas.filters.WorkPoolFilter = None,
    work_queue_filter: schemas.filters.WorkQueueFilter = None,
    sort: schemas.sorting.DeploymentSort = schemas.sorting.DeploymentSort.NAME_ASC,
):
    """
    Read deployments.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
        flow_filter: only select deployments whose flows match these criteria
        flow_run_filter: only select deployments whose flow runs match these criteria
        task_run_filter: only select deployments whose task runs match these criteria
        deployment_filter: only select deployment that match these filters
        work_pool_filter: only select deployments whose work pools match these criteria
        work_queue_filter: only select deployments whose work pool queues match these criteria
        sort: the sort criteria for selected deployments. Defaults to `name` ASC.

    Returns:
        List[db.Deployment]: deployments
    """

    query = select(db.Deployment).order_by(sort.as_sql_sort(db=db))

    query = await _apply_deployment_filters(
        query=query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
        work_queue_filter=work_queue_filter,
        db=db,
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def count_deployments(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    work_pool_filter: schemas.filters.WorkPoolFilter = None,
    work_queue_filter: schemas.filters.WorkQueueFilter = None,
) -> int:
    """
    Count deployments.

    Args:
        session: A database session
        flow_filter: only count deployments whose flows match these criteria
        flow_run_filter: only count deployments whose flow runs match these criteria
        task_run_filter: only count deployments whose task runs match these criteria
        deployment_filter: only count deployment that match these filters
        work_pool_filter: only count deployments that match these work pool filters
        work_queue_filter: only count deployments that match these work pool queue filters

    Returns:
        int: the number of deployments matching filters
    """

    query = select(sa.func.count(sa.text("*"))).select_from(db.Deployment)

    query = await _apply_deployment_filters(
        query=query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
        work_queue_filter=work_queue_filter,
        db=db,
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def delete_deployment(
    session: sa.orm.Session, deployment_id: UUID, db: PrefectDBInterface
) -> bool:
    """
    Delete a deployment by id.

    Args:
        session: A database session
        deployment_id: a deployment id

    Returns:
        bool: whether or not the deployment was deleted
    """

    # delete scheduled runs, both auto- and user- created.
    await _delete_scheduled_runs(
        session=session, deployment_id=deployment_id, auto_scheduled_only=False
    )

    result = await session.execute(
        delete(db.Deployment).where(db.Deployment.id == deployment_id)
    )
    return result.rowcount > 0


async def schedule_runs(
    session: sa.orm.Session,
    deployment_id: UUID,
    start_time: datetime.datetime = None,
    end_time: datetime.datetime = None,
    min_time: datetime.timedelta = None,
    min_runs: int = None,
    max_runs: int = None,
    auto_scheduled: bool = True,
) -> List[UUID]:
    """
    Schedule flow runs for a deployment

    Args:
        session: a database session
        deployment_id: the id of the deployment to schedule
        start_time: the time from which to start scheduling runs
        end_time: runs will be scheduled until at most this time
        min_time: runs will be scheduled until at least this far in the future
        min_runs: a minimum amount of runs to schedule
        max_runs: a maximum amount of runs to schedule

    This function will generate the minimum number of runs that satisfy the min
    and max times, and the min and max counts. Specifically, the following order
    will be respected.

        - Runs will be generated starting on or after the `start_time`
        - No more than `max_runs` runs will be generated
        - No runs will be generated after `end_time` is reached
        - At least `min_runs` runs will be generated
        - Runs will be generated until at least `start_time` + `min_time` is reached

    Returns:
        a list of flow run ids scheduled for the deployment
    """
    if min_runs is None:
        min_runs = PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()
    if max_runs is None:
        max_runs = PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS.value()
    if start_time is None:
        start_time = pendulum.now("UTC")
    if end_time is None:
        end_time = start_time + (
            PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
        )
    if min_time is None:
        min_time = PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME.value()

    start_time = pendulum.instance(start_time)
    end_time = pendulum.instance(end_time)

    runs = await _generate_scheduled_flow_runs(
        session=session,
        deployment_id=deployment_id,
        start_time=start_time,
        end_time=end_time,
        min_time=min_time,
        min_runs=min_runs,
        max_runs=max_runs,
        auto_scheduled=auto_scheduled,
    )
    return await _insert_scheduled_flow_runs(session=session, runs=runs)


@inject_db
async def _generate_scheduled_flow_runs(
    session: sa.orm.Session,
    deployment_id: UUID,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    min_time: datetime.timedelta,
    min_runs: int,
    max_runs: int,
    db: PrefectDBInterface,
    auto_scheduled: bool = True,
) -> List[Dict]:
    """
    Given a `deployment_id` and schedule, generates a list of flow run objects and
    associated scheduled states that represent scheduled flow runs. This method
    does NOT insert generated runs into the database, in order to facilitate
    batch operations. Call `_insert_scheduled_flow_runs()` to insert these runs.

    Runs include an idempotency key which prevents duplicate runs from being inserted
    if the output from this function is used more than once.

    Args:
        session: a database session
        deployment_id: the id of the deployment to schedule
        start_time: the time from which to start scheduling runs
        end_time: runs will be scheduled until at most this time
        min_time: runs will be scheduled until at least this far in the future
        min_runs: a minimum amount of runs to schedule
        max_runs: a maximum amount of runs to schedule

    This function will generate the minimum number of runs that satisfy the min
    and max times, and the min and max counts. Specifically, the following order
    will be respected.

        - Runs will be generated starting on or after the `start_time`
        - No more than `max_runs` runs will be generated
        - No runs will be generated after `end_time` is reached
        - At least `min_runs` runs will be generated
        - Runs will be generated until at least `start_time + min_time` is reached

    Returns:
        a list of dictionary representations of the `FlowRun` objects to schedule
    """
    runs = []

    # retrieve the deployment
    deployment = await session.get(db.Deployment, deployment_id)

    if not deployment or not deployment.schedule or not deployment.is_schedule_active:
        return []

    dates = []

    # generate up to `n` dates satisfying the min of `max_runs` and `end_time`
    for dt in deployment.schedule._get_dates_generator(
        n=max_runs, start=start_time, end=end_time
    ):
        dates.append(dt)

        # at any point, if we satisfy both of the minimums, we can stop
        if len(dates) >= min_runs and dt >= (start_time + min_time):
            break

    tags = deployment.tags
    if auto_scheduled:
        tags = ["auto-scheduled"] + tags

    for date in dates:
        runs.append(
            {
                "id": uuid4(),
                "flow_id": deployment.flow_id,
                "deployment_id": deployment_id,
                "work_queue_name": deployment.work_queue_name,
                "work_queue_id": deployment.work_queue_id,
                "parameters": deployment.parameters,
                "infrastructure_document_id": deployment.infrastructure_document_id,
                "idempotency_key": f"scheduled {deployment.id} {date}",
                "tags": tags,
                "auto_scheduled": auto_scheduled,
                "state": schemas.states.Scheduled(
                    scheduled_time=date,
                    message="Flow run scheduled",
                ).dict(),
                "state_type": schemas.states.StateType.SCHEDULED,
                "state_name": "Scheduled",
                "next_scheduled_start_time": date,
                "expected_start_time": date,
            }
        )

    return runs


@inject_db
async def _insert_scheduled_flow_runs(
    session: sa.orm.Session, runs: List[Dict], db: PrefectDBInterface
) -> List[UUID]:
    """
    Given a list of flow runs to schedule, as generated by `_generate_scheduled_flow_runs`,
    inserts them into the database. Note this is a separate method to facilitate batch
    operations on many scheduled runs.

    Args:
        session: a database session
        runs: a list of dicts representing flow runs to insert

    Returns:
        a list of flow run ids that were created
    """

    if not runs:
        return []

    # gracefully insert the flow runs against the idempotency key
    # this syntax (insert statement, values to insert) is most efficient
    # because it uses a single bind parameter
    insert = await db.insert(db.FlowRun)
    await session.execute(
        insert.on_conflict_do_nothing(index_elements=db.flow_run_unique_upsert_columns),
        runs,
    )

    # query for the rows that were newly inserted (by checking for any flow runs with
    # no corresponding flow run states)
    inserted_rows = (
        sa.select(db.FlowRun.id)
        .join(
            db.FlowRunState,
            db.FlowRun.id == db.FlowRunState.flow_run_id,
            isouter=True,
        )
        .where(
            db.FlowRun.id.in_([r["id"] for r in runs]),
            db.FlowRunState.id.is_(None),
        )
    )
    inserted_flow_run_ids = (await session.execute(inserted_rows)).scalars().all()

    # insert flow run states that correspond to the newly-insert rows
    insert_flow_run_states = [
        {"id": uuid4(), "flow_run_id": r["id"], **r["state"]}
        for r in runs
        if r["id"] in inserted_flow_run_ids
    ]
    if insert_flow_run_states:
        # this syntax (insert statement, values to insert) is most efficient
        # because it uses a single bind parameter
        await session.execute(
            db.FlowRunState.__table__.insert(), insert_flow_run_states
        )

        # set the `state_id` on the newly inserted runs
        stmt = db.set_state_id_on_inserted_flow_runs_statement(
            inserted_flow_run_ids=inserted_flow_run_ids,
            insert_flow_run_states=insert_flow_run_states,
        )

        await session.execute(stmt)

    return inserted_flow_run_ids


@inject_db
async def check_work_queues_for_deployment(
    db: PrefectDBInterface, session: sa.orm.Session, deployment_id: UUID
) -> List[schemas.core.WorkQueue]:
    """
    Get work queues that can pick up the specified deployment.

    Work queues will pick up a deployment when all of the following are met.

    - The deployment has ALL tags that the work queue has (i.e. the work
    queue's tags must be a subset of the deployment's tags).
    - The work queue's specified deployment IDs match the deployment's ID,
    or the work queue does NOT have specified deployment IDs.
    - The work queue's specified flow runners match the deployment's flow
    runner or the work queue does NOT have a specified flow runner.

    Notes on the query:

    - Our database currently allows either "null" and empty lists as
    null values in filters, so we need to catch both cases with "or".
    - `json_contains(A, B)` should be interepreted as "True if A
    contains B".

    Returns:
        List[db.WorkQueue]: WorkQueues
    """
    deployment = await session.get(db.Deployment, deployment_id)
    if not deployment:
        raise ObjectNotFoundError(f"Deployment with id {deployment_id} not found")

    query = (
        select(db.WorkQueue)
        # work queue tags are a subset of deployment tags
        .filter(
            or_(
                json_contains(deployment.tags, db.WorkQueue.filter["tags"]),
                json_contains([], db.WorkQueue.filter["tags"]),
                json_contains(None, db.WorkQueue.filter["tags"]),
            )
        )
        # deployment_ids is null or contains the deployment's ID
        .filter(
            or_(
                json_contains(
                    db.WorkQueue.filter["deployment_ids"],
                    str(deployment.id),
                ),
                json_contains(None, db.WorkQueue.filter["deployment_ids"]),
                json_contains([], db.WorkQueue.filter["deployment_ids"]),
            )
        )
    )

    result = await session.execute(query)
    return result.scalars().unique().all()
