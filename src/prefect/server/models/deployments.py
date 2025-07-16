"""
Functions for interacting with deployment ORM objects.
Intended for internal use by the Prefect REST API.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, Optional, TypeVar, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from prefect._internal.uuid7 import uuid7
from prefect.logging import get_logger
from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, db_injector, orm_models
from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models.events import deployment_status_event
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME,
)
from prefect.types._datetime import DateTime, now

T = TypeVar("T", bound=tuple[Any, ...])

logger: logging.Logger = get_logger("prefect.server.models.deployments")


@db_injector
async def _delete_scheduled_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    auto_scheduled_only: bool = False,
    future_only: bool = False,
) -> None:
    """
    This utility function deletes all of a deployment's runs that are in a Scheduled state
    and haven't run yet. It should be run any time a deployment is created or
    modified in order to ensure that future runs comply with the deployment's latest values.

    Args:
        deployment_id: the deployment for which we should delete runs.
        auto_scheduled_only: if True, only delete auto scheduled runs. Defaults to `False`.
        future_only: if True, only delete runs that are scheduled to run in the future.
            Defaults to `False`.
    """
    delete_query = sa.delete(db.FlowRun).where(
        db.FlowRun.deployment_id == deployment_id,
        db.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
        db.FlowRun.state_name != schemas.states.AwaitingConcurrencySlot().name,
        db.FlowRun.run_count == 0,
    )

    if auto_scheduled_only:
        delete_query = delete_query.where(
            db.FlowRun.auto_scheduled.is_(True),
        )

    if future_only:
        delete_query = delete_query.where(
            db.FlowRun.next_scheduled_start_time > now("UTC"),
        )

    await session.execute(delete_query)


@db_injector
async def create_deployment(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment: schemas.core.Deployment | schemas.actions.DeploymentCreate,
) -> Optional[orm_models.Deployment]:
    """Upserts a deployment.

    Args:
        session: a database session
        deployment: a deployment model

    Returns:
        orm_models.Deployment: the newly-created or updated deployment

    """

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    deployment.updated = now("UTC")  # type: ignore[assignment]

    deployment.labels = await with_system_labels_for_deployment(session, deployment)

    schedules = deployment.schedules
    insert_values = deployment.model_dump_for_orm(
        exclude_unset=True, exclude={"schedules", "version_info"}
    )

    requested_concurrency_limit = insert_values.pop("concurrency_limit", "unset")

    # The job_variables field in client and server schemas is named
    # infra_overrides in the database.
    job_variables = insert_values.pop("job_variables", None)
    if job_variables:
        insert_values["infra_overrides"] = job_variables

    conflict_update_fields = deployment.model_dump_for_orm(
        exclude_unset=True,
        exclude={
            "id",
            "created",
            "created_by",
            "schedules",
            "job_variables",
            "concurrency_limit",
            "version_info",
        },
    )
    if job_variables:
        conflict_update_fields["infra_overrides"] = job_variables

    insert_stmt = (
        db.queries.insert(db.Deployment)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=db.orm.deployment_unique_upsert_columns,
            set_={**conflict_update_fields},
        )
    )

    await session.execute(insert_stmt)

    # Get the id of the deployment we just created or updated
    result = await session.execute(
        sa.select(db.Deployment.id).where(
            sa.and_(
                db.Deployment.flow_id == deployment.flow_id,
                db.Deployment.name == deployment.name,
            )
        )
    )
    deployment_id = result.scalar_one_or_none()

    if not deployment_id:
        return None

    # Because this was possibly an upsert, we need to delete any existing
    # schedules and any runs from the old deployment.

    await _delete_scheduled_runs(
        session=session,
        deployment_id=deployment_id,
        auto_scheduled_only=True,
        future_only=True,
    )

    await delete_schedules_for_deployment(session=session, deployment_id=deployment_id)

    if schedules:
        await create_deployment_schedules(
            session=session,
            deployment_id=deployment_id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule.schedule,
                    active=schedule.active,
                    parameters=schedule.parameters,
                    slug=schedule.slug,
                )
                for schedule in schedules
            ],
        )

    if requested_concurrency_limit != "unset":
        await _create_or_update_deployment_concurrency_limit(
            db, session, deployment_id, deployment.concurrency_limit
        )

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
    refreshed_result = await session.execute(query)
    return refreshed_result.scalar()


@db_injector
async def update_deployment(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    deployment: schemas.actions.DeploymentUpdate,
) -> bool:
    """Updates a deployment.

    Args:
        session: a database session
        deployment_id: the ID of the deployment to modify
        deployment: changes to a deployment model

    Returns:
        bool: whether the deployment was updated

    """

    from prefect.server.api.workers import WorkerLookups

    schedules = deployment.schedules

    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = deployment.model_dump_for_orm(
        exclude_unset=True,
        exclude={"work_pool_name", "version_info"},
    )

    requested_global_concurrency_limit_update = update_data.pop(
        "global_concurrency_limit_id", "unset"
    )
    requested_concurrency_limit_update = update_data.pop("concurrency_limit", "unset")

    if requested_global_concurrency_limit_update != "unset":
        update_data["concurrency_limit_id"] = requested_global_concurrency_limit_update

    # The job_variables field in client and server schemas is named
    # infra_overrides in the database.
    job_variables = update_data.pop("job_variables", None)
    if job_variables:
        update_data["infra_overrides"] = job_variables

    should_update_schedules = update_data.pop("schedules", None) is not None

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
        work_queue = await models.work_queues.ensure_work_queue_exists(
            session=session, name=update_data["work_queue_name"]
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
        session=session,
        deployment_id=deployment_id,
        auto_scheduled_only=True,
        future_only=True,
    )

    if should_update_schedules:
        # If schedules were provided, remove the existing schedules and
        # replace them with the new ones.
        await delete_schedules_for_deployment(
            session=session, deployment_id=deployment_id
        )
        await create_deployment_schedules(
            session=session,
            deployment_id=deployment_id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule.schedule,
                    active=schedule.active if schedule.active is not None else True,
                    parameters=schedule.parameters,
                    slug=schedule.slug,
                )
                for schedule in schedules
                if schedule.schedule is not None
            ],
        )

    if requested_concurrency_limit_update != "unset":
        await _create_or_update_deployment_concurrency_limit(
            db, session, deployment_id, deployment.concurrency_limit
        )

    return result.rowcount > 0


async def _create_or_update_deployment_concurrency_limit(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    limit: Optional[int],
):
    deployment = await session.get(db.Deployment, deployment_id)
    assert deployment is not None

    if (
        deployment.global_concurrency_limit
        and deployment.global_concurrency_limit.limit == limit
    ) or (deployment.global_concurrency_limit is None and limit is None):
        return

    deployment._concurrency_limit = limit
    if limit is None:
        await _delete_related_concurrency_limit(
            db, session=session, deployment_id=deployment_id
        )
        await session.refresh(deployment)
    elif deployment.global_concurrency_limit:
        deployment.global_concurrency_limit.limit = limit
    else:
        limit_name = f"deployment:{deployment_id}"
        new_limit = db.ConcurrencyLimitV2(name=limit_name, limit=limit)
        deployment.global_concurrency_limit = new_limit

    session.add(deployment)


@db_injector
async def read_deployment(
    db: PrefectDBInterface, session: AsyncSession, deployment_id: UUID
) -> Optional[orm_models.Deployment]:
    """Reads a deployment by id.

    Args:
        session: A database session
        deployment_id: a deployment id

    Returns:
        orm_models.Deployment: the deployment
    """

    return await session.get(db.Deployment, deployment_id)


@db_injector
async def read_deployment_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str, flow_name: str
) -> Optional[orm_models.Deployment]:
    """Reads a deployment by name.

    Args:
        session: A database session
        name: a deployment name
        flow_name: the name of the flow the deployment belongs to

    Returns:
        orm_models.Deployment: the deployment
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


async def _apply_deployment_filters(
    db: PrefectDBInterface,
    query: Select[T],
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
    work_pool_filter: Optional[schemas.filters.WorkPoolFilter] = None,
    work_queue_filter: Optional[schemas.filters.WorkQueueFilter] = None,
) -> Select[T]:
    """
    Applies filters to a deployment query as a combination of EXISTS subqueries.
    """

    if deployment_filter:
        query = query.where(deployment_filter.as_sql_filter())

    if flow_filter:
        flow_exists_clause = select(db.Deployment.id).where(
            db.Deployment.flow_id == db.Flow.id,
            flow_filter.as_sql_filter(),
        )

        query = query.where(flow_exists_clause.exists())

    if flow_run_filter or task_run_filter:
        flow_run_exists_clause = select(db.FlowRun).where(
            db.Deployment.id == db.FlowRun.deployment_id
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

    if work_pool_filter or work_queue_filter:
        work_pool_exists_clause = select(db.WorkQueue).where(
            db.Deployment.work_queue_id == db.WorkQueue.id
        )

        if work_queue_filter:
            work_pool_exists_clause = work_pool_exists_clause.where(
                work_queue_filter.as_sql_filter()
            )

        if work_pool_filter:
            work_pool_exists_clause = work_pool_exists_clause.join(
                db.WorkPool,
                db.WorkPool.id == db.WorkQueue.work_pool_id,
            ).where(work_pool_filter.as_sql_filter())

        query = query.where(work_pool_exists_clause.exists())

    return query


@db_injector
async def read_deployments(
    db: PrefectDBInterface,
    session: AsyncSession,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
    work_pool_filter: Optional[schemas.filters.WorkPoolFilter] = None,
    work_queue_filter: Optional[schemas.filters.WorkQueueFilter] = None,
    sort: schemas.sorting.DeploymentSort = schemas.sorting.DeploymentSort.NAME_ASC,
) -> Sequence[orm_models.Deployment]:
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
        list[orm_models.Deployment]: deployments
    """

    query = select(db.Deployment).order_by(*sort.as_sql_sort())

    query = await _apply_deployment_filters(
        db,
        query=query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
        work_queue_filter=work_queue_filter,
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def count_deployments(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
    work_pool_filter: Optional[schemas.filters.WorkPoolFilter] = None,
    work_queue_filter: Optional[schemas.filters.WorkQueueFilter] = None,
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

    query = select(sa.func.count(None)).select_from(db.Deployment)

    query = await _apply_deployment_filters(
        db,
        query=query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        work_pool_filter=work_pool_filter,
        work_queue_filter=work_queue_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


@db_injector
async def delete_deployment(
    db: PrefectDBInterface, session: AsyncSession, deployment_id: UUID
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

    await _delete_related_concurrency_limit(
        db, session=session, deployment_id=deployment_id
    )

    result = await session.execute(
        delete(db.Deployment).where(db.Deployment.id == deployment_id)
    )
    return result.rowcount > 0


async def _delete_related_concurrency_limit(
    db: PrefectDBInterface, session: AsyncSession, deployment_id: UUID
):
    return await session.execute(
        delete(db.ConcurrencyLimitV2).where(
            db.ConcurrencyLimitV2.id
            == sa.select(db.Deployment.concurrency_limit_id)
            .where(db.Deployment.id == deployment_id)
            .scalar_subquery()
        )
    )


@db_injector
async def schedule_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
    min_time: Optional[datetime.timedelta] = None,
    min_runs: Optional[int] = None,
    max_runs: Optional[int] = None,
    auto_scheduled: bool = True,
) -> Sequence[UUID]:
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
        assert min_runs is not None
    if max_runs is None:
        max_runs = PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS.value()
        assert max_runs is not None
    if start_time is None:
        start_time = now("UTC")
    if end_time is None:
        end_time = start_time + (
            PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value()
        )
    if min_time is None:
        min_time = PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME.value()
        assert min_time is not None

    actual_start_time = start_time
    if TYPE_CHECKING:
        assert end_time is not None
    actual_end_time = end_time

    runs = await _generate_scheduled_flow_runs(
        db,
        session=session,
        deployment_id=deployment_id,
        start_time=actual_start_time,
        end_time=actual_end_time,
        min_time=min_time,
        min_runs=min_runs,
        max_runs=max_runs,
        auto_scheduled=auto_scheduled,
    )
    return await _insert_scheduled_flow_runs(session=session, runs=runs)


async def _generate_scheduled_flow_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    min_time: datetime.timedelta,
    min_runs: int,
    max_runs: int,
    auto_scheduled: bool = True,
) -> list[dict[str, Any]]:
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
    runs: list[dict[str, Any]] = []

    deployment = await session.get(db.Deployment, deployment_id)

    if not deployment:
        return []

    active_deployment_schedules = await read_deployment_schedules(
        session=session,
        deployment_id=deployment.id,
        deployment_schedule_filter=schemas.filters.DeploymentScheduleFilter(
            active=schemas.filters.DeploymentScheduleFilterActive(eq_=True)
        ),
    )

    for deployment_schedule in active_deployment_schedules:
        dates: list[DateTime] = []

        # generate up to `n` dates satisfying the min of `max_runs` and `end_time`
        for dt in deployment_schedule.schedule._get_dates_generator(
            n=max_runs, start=start_time, end=end_time
        ):
            dates.append(dt)

            # at any point, if we satisfy both of the minimums, we can stop
            if len(dates) >= min_runs and dt >= (start_time + min_time):
                break

        tags = deployment.tags
        if auto_scheduled:
            tags = ["auto-scheduled"] + tags

        parameters = {
            **deployment.parameters,
            **deployment_schedule.parameters,
        }

        # Generate system labels for flow runs from this deployment
        labels = await with_system_labels_for_deployment_flow_run(
            session=session,
            deployment=deployment,
        )

        for date in dates:
            runs.append(
                {
                    "id": uuid7(),
                    "flow_id": deployment.flow_id,
                    "deployment_id": deployment_id,
                    "deployment_version": deployment.version,
                    "work_queue_name": deployment.work_queue_name,
                    "work_queue_id": deployment.work_queue_id,
                    "parameters": parameters,
                    "infrastructure_document_id": deployment.infrastructure_document_id,
                    "idempotency_key": f"scheduled {deployment.id} {deployment_schedule.id} {date}",
                    "tags": tags,
                    "labels": labels,
                    "auto_scheduled": auto_scheduled,
                    "state": schemas.states.Scheduled(
                        scheduled_time=date,
                        message="Flow run scheduled",
                    ).model_dump(),
                    "state_type": schemas.states.StateType.SCHEDULED,
                    "state_name": "Scheduled",
                    "next_scheduled_start_time": date,
                    "expected_start_time": date,
                    "created_by": {
                        "id": deployment_schedule.id,
                        "display_value": deployment_schedule.slug
                        or deployment_schedule.schedule.__class__.__name__,
                        "type": "SCHEDULE",
                    },
                }
            )

    return runs


@db_injector
async def _insert_scheduled_flow_runs(
    db: PrefectDBInterface, session: AsyncSession, runs: list[dict[str, Any]]
) -> Sequence[UUID]:
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
    await session.execute(
        db.queries.insert(db.FlowRun).on_conflict_do_nothing(
            index_elements=db.orm.flow_run_unique_upsert_columns
        ),
        runs,
    )

    # query for the rows that were newly inserted (by checking for any flow runs with
    # no corresponding flow run states)
    inserted_rows = sa.select(db.FlowRun.id).where(
        db.FlowRun.id.in_([r["id"] for r in runs]),
        ~select(db.FlowRunState.id)
        .where(db.FlowRunState.flow_run_id == db.FlowRun.id)
        .exists(),
    )
    inserted_flow_run_ids = (await session.execute(inserted_rows)).scalars().all()

    # insert flow run states that correspond to the newly-insert rows
    insert_flow_run_states: list[dict[str, Any]] = [
        {"id": uuid7(), "flow_run_id": r["id"], **r["state"]}
        for r in runs
        if r["id"] in inserted_flow_run_ids
    ]
    if insert_flow_run_states:
        # this syntax (insert statement, values to insert) is most efficient
        # because it uses a single bind parameter
        await session.execute(
            db.FlowRunState.__table__.insert(),  # type: ignore[attr-defined]
            insert_flow_run_states,
        )

        # set the `state_id` on the newly inserted runs
        stmt = db.queries.set_state_id_on_inserted_flow_runs_statement(
            inserted_flow_run_ids=inserted_flow_run_ids,
            insert_flow_run_states=insert_flow_run_states,
        )

        await session.execute(stmt)

    return inserted_flow_run_ids


@db_injector
async def check_work_queues_for_deployment(
    db: PrefectDBInterface, session: AsyncSession, deployment_id: UUID
) -> Sequence[orm_models.WorkQueue]:
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
    - `A.contains(B)` should be interpreted as "True if A
    contains B".

    Returns:
        List[orm_models.WorkQueue]: WorkQueues
    """
    deployment = await session.get(db.Deployment, deployment_id)
    if not deployment:
        raise ObjectNotFoundError(f"Deployment with id {deployment_id} not found")

    def json_contains(a: Any, b: Any) -> sa.ColumnElement[bool]:
        return sa.type_coerce(a, type_=JSONB).contains(sa.type_coerce(b, type_=JSONB))

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


@db_injector
async def create_deployment_schedules(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    schedules: list[schemas.actions.DeploymentScheduleCreate],
) -> list[schemas.core.DeploymentSchedule]:
    """
    Creates a deployment's schedules.

    Args:
        session: A database session
        deployment_id: a deployment id
        schedules: a list of deployment schedule create actions
    """

    schedules_with_deployment_id: list[dict[str, Any]] = []
    for schedule in schedules:
        data = schedule.model_dump()
        data["deployment_id"] = deployment_id
        schedules_with_deployment_id.append(data)

    models = [
        db.DeploymentSchedule(**schedule) for schedule in schedules_with_deployment_id
    ]
    session.add_all(models)
    await session.flush()

    return [
        schemas.core.DeploymentSchedule.model_validate(m, from_attributes=True)
        for m in models
    ]


@db_injector
async def read_deployment_schedules(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    deployment_schedule_filter: Optional[
        schemas.filters.DeploymentScheduleFilter
    ] = None,
) -> list[schemas.core.DeploymentSchedule]:
    """
    Reads a deployment's schedules.

    Args:
        session: A database session
        deployment_id: a deployment id

    Returns:
        list[schemas.core.DeploymentSchedule]: the deployment's schedules
    """

    query = (
        sa.select(db.DeploymentSchedule)
        .where(db.DeploymentSchedule.deployment_id == deployment_id)
        .order_by(db.DeploymentSchedule.updated.desc())
    )

    if deployment_schedule_filter:
        query = query.where(deployment_schedule_filter.as_sql_filter())

    result = await session.execute(query)

    return [
        schemas.core.DeploymentSchedule.model_validate(s, from_attributes=True)
        for s in result.scalars().all()
    ]


@db_injector
async def update_deployment_schedule(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    schedule: schemas.actions.DeploymentScheduleUpdate,
    deployment_schedule_id: UUID | None = None,
    deployment_schedule_slug: str | None = None,
) -> bool:
    """
    Updates a deployment's schedules.

    Args:
        session: A database session
        deployment_schedule_id: a deployment schedule id
        schedule: a deployment schedule update action
    """
    if deployment_schedule_id:
        result = await session.execute(
            sa.update(db.DeploymentSchedule)
            .where(
                sa.and_(
                    db.DeploymentSchedule.id == deployment_schedule_id,
                    db.DeploymentSchedule.deployment_id == deployment_id,
                )
            )
            .values(**schedule.model_dump(exclude_none=True))
        )
    elif deployment_schedule_slug:
        result = await session.execute(
            sa.update(db.DeploymentSchedule)
            .where(
                sa.and_(
                    db.DeploymentSchedule.slug == deployment_schedule_slug,
                    db.DeploymentSchedule.deployment_id == deployment_id,
                )
            )
            .values(**schedule.model_dump(exclude_none=True))
        )
    else:
        raise ValueError(
            "Either deployment_schedule_id or deployment_schedule_slug must be provided"
        )

    return result.rowcount > 0


@db_injector
async def delete_schedules_for_deployment(
    db: PrefectDBInterface, session: AsyncSession, deployment_id: UUID
) -> bool:
    """
    Deletes a deployment schedule.

    Args:
        session: A database session
        deployment_id: a deployment id
    """

    deployment = await session.get(db.Deployment, deployment_id)
    assert deployment is not None

    result = await session.execute(
        sa.delete(db.DeploymentSchedule).where(
            db.DeploymentSchedule.deployment_id == deployment_id
        )
    )

    await session.refresh(deployment)
    return result.rowcount > 0


@db_injector
async def delete_deployment_schedule(
    db: PrefectDBInterface,
    session: AsyncSession,
    deployment_id: UUID,
    deployment_schedule_id: UUID,
) -> bool:
    """
    Deletes a deployment schedule.

    Args:
        session: A database session
        deployment_schedule_id: a deployment schedule id
    """

    result = await session.execute(
        sa.delete(db.DeploymentSchedule).where(
            sa.and_(
                db.DeploymentSchedule.id == deployment_schedule_id,
                db.DeploymentSchedule.deployment_id == deployment_id,
            )
        )
    )

    return result.rowcount > 0


async def mark_deployments_ready(
    db: PrefectDBInterface,
    deployment_ids: Optional[Iterable[UUID]] = None,
    work_queue_ids: Optional[Iterable[UUID]] = None,
) -> None:
    try:
        deployment_ids = deployment_ids or []
        work_queue_ids = work_queue_ids or []

        if not deployment_ids and not work_queue_ids:
            return

        async with db.session_context(
            begin_transaction=True,
        ) as session:
            result = await session.execute(
                select(db.Deployment.id).where(
                    sa.or_(
                        db.Deployment.id.in_(deployment_ids),
                        db.Deployment.work_queue_id.in_(work_queue_ids),
                    ),
                    db.Deployment.status == DeploymentStatus.NOT_READY,
                )
            )
            unready_deployments = list(result.scalars().unique().all())

            last_polled = now("UTC")

            await session.execute(
                sa.update(db.Deployment)
                .where(
                    sa.or_(
                        db.Deployment.id.in_(deployment_ids),
                        db.Deployment.work_queue_id.in_(work_queue_ids),
                    )
                )
                .values(status=DeploymentStatus.READY, last_polled=last_polled)
            )

            if not unready_deployments:
                return

            async with PrefectServerEventsClient() as events:
                for deployment_id in unready_deployments:
                    await events.emit(
                        await deployment_status_event(
                            session=session,
                            deployment_id=deployment_id,
                            status=DeploymentStatus.READY,
                            occurred=last_polled,
                        )
                    )
    except Exception as exc:
        logger.error(f"Error marking deployments as ready: {exc}", exc_info=True)


@db_injector
async def mark_deployments_not_ready(
    db: PrefectDBInterface,
    deployment_ids: Optional[Iterable[UUID]] = None,
    work_queue_ids: Optional[Iterable[UUID]] = None,
) -> None:
    try:
        deployment_ids = deployment_ids or []
        work_queue_ids = work_queue_ids or []

        if not deployment_ids and not work_queue_ids:
            return

        async with db.session_context(
            begin_transaction=True,
        ) as session:
            result = await session.execute(
                select(db.Deployment.id).where(
                    sa.or_(
                        db.Deployment.id.in_(deployment_ids),
                        db.Deployment.work_queue_id.in_(work_queue_ids),
                    ),
                    db.Deployment.status == DeploymentStatus.READY,
                )
            )
            ready_deployments = list(result.scalars().unique().all())

            await session.execute(
                sa.update(db.Deployment)
                .where(
                    sa.or_(
                        db.Deployment.id.in_(deployment_ids),
                        db.Deployment.work_queue_id.in_(work_queue_ids),
                    )
                )
                .values(status=DeploymentStatus.NOT_READY)
            )

            if not ready_deployments:
                return

            async with PrefectServerEventsClient() as events:
                for deployment_id in ready_deployments:
                    await events.emit(
                        await deployment_status_event(
                            session=session,
                            deployment_id=deployment_id,
                            status=DeploymentStatus.NOT_READY,
                            occurred=now("UTC"),
                        )
                    )
    except Exception as exc:
        logger.error(f"Error marking deployments as not ready: {exc}", exc_info=True)


async def with_system_labels_for_deployment(
    session: AsyncSession,
    deployment: schemas.core.Deployment,
) -> schemas.core.KeyValueLabels:
    """Augment user supplied labels with system default labels for a deployment."""
    default_labels = cast(
        schemas.core.KeyValueLabels,
        {
            "prefect.flow.id": str(deployment.flow_id),
        },
    )

    user_supplied_labels = deployment.labels or {}

    parent_labels = (
        await models.flows.read_flow_labels(session, deployment.flow_id)
    ) or {}

    return parent_labels | default_labels | user_supplied_labels


async def with_system_labels_for_deployment_flow_run(
    session: AsyncSession,
    deployment: orm_models.Deployment,
    user_supplied_labels: Optional[schemas.core.KeyValueLabels] = None,
) -> schemas.core.KeyValueLabels:
    """Generate system labels for a flow run created from a deployment.

    Args:
        session: Database session
        deployment: The deployment the flow run is created from
        user_supplied_labels: Optional user-supplied labels to include

    Returns:
        Complete set of labels for the flow run
    """
    system_labels = cast(
        schemas.core.KeyValueLabels,
        {
            "prefect.flow.id": str(deployment.flow_id),
            "prefect.deployment.id": str(deployment.id),
        },
    )

    # Use deployment labels as parent labels for flow runs
    parent_labels = deployment.labels or {}
    user_labels = user_supplied_labels or {}

    return parent_labels | system_labels | user_labels
