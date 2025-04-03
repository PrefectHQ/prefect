"""
Functions for interacting with task run ORM objects.
Intended for internal use by the Prefect REST API.
"""

import contextlib
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, db_injector, orm_models
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.orchestration.core_policy import (
    BackgroundTaskPolicy,
    MinimalTaskPolicy,
)
from prefect.server.orchestration.global_policy import GlobalTaskPolicy
from prefect.server.orchestration.policies import (
    TaskRunOrchestrationPolicy,
)
from prefect.server.orchestration.rules import TaskOrchestrationContext
from prefect.server.schemas.responses import OrchestrationResult
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

T = TypeVar("T", bound=tuple[Any, ...])

logger: "logging.Logger" = get_logger("server")


@db_injector
async def create_task_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    task_run: schemas.core.TaskRun,
    orchestration_parameters: Optional[Dict[str, Any]] = None,
) -> orm_models.TaskRun:
    """
    Creates a new task run.

    If a task run with the same flow_run_id, task_key, and dynamic_key already exists,
    the existing task run will be returned. If the provided task run has a state
    attached, it will also be created.

    Args:
        session: a database session
        task_run: a task run model

    Returns:
        orm_models.TaskRun: the newly-created or existing task run
    """

    right_now = now("UTC")
    model: Union[orm_models.TaskRun, None]

    task_run.labels = await with_system_labels_for_task_run(
        session=session, task_run=task_run
    )

    # if a dynamic key exists, we need to guard against conflicts
    if task_run.flow_run_id:
        insert_stmt = (
            db.queries.insert(db.TaskRun)
            .values(
                created=right_now,
                **task_run.model_dump_for_orm(
                    exclude={"state", "created"}, exclude_unset=True
                ),
            )
            .on_conflict_do_nothing(
                index_elements=db.orm.task_run_unique_upsert_columns,
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
        model = result.scalar_one()
    else:
        # Upsert on (task_key, dynamic_key) application logic.
        query = (
            sa.select(db.TaskRun)
            .where(
                sa.and_(
                    db.TaskRun.flow_run_id.is_(None),
                    db.TaskRun.task_key == task_run.task_key,
                    db.TaskRun.dynamic_key == task_run.dynamic_key,
                )
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )

        result = await session.execute(query)
        model = result.scalar()

        if model is None:
            model = db.TaskRun(
                created=right_now,
                **task_run.model_dump_for_orm(
                    exclude={"state", "created"}, exclude_unset=True
                ),
                state=None,
            )
            session.add(model)
            await session.flush()

    if model.created == right_now and task_run.state:
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=model.id,
            state=task_run.state,
            force=True,
            orchestration_parameters=orchestration_parameters,
        )

    return model


@db_injector
async def update_task_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    task_run_id: UUID,
    task_run: schemas.actions.TaskRunUpdate,
) -> bool:
    """
    Updates a task run.

    Args:
        session: a database session
        task_run_id: the task run id to update
        task_run: a task run model

    Returns:
        bool: whether or not matching rows were found to update
    """
    update_stmt = (
        sa.update(db.TaskRun)
        .where(db.TaskRun.id == task_run_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**task_run.model_dump_for_orm(exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@db_injector
async def read_task_run(
    db: PrefectDBInterface, session: AsyncSession, task_run_id: UUID
) -> Union[orm_models.TaskRun, None]:
    """
    Read a task run by id.

    Args:
        session: a database session
        task_run_id: the task run id

    Returns:
        orm_models.TaskRun: the task run
    """

    model = await session.get(db.TaskRun, task_run_id)
    return model


@db_injector
async def read_task_run_with_flow_run_name(
    db: PrefectDBInterface, session: AsyncSession, task_run_id: UUID
) -> Union[orm_models.TaskRun, None]:
    """
    Read a task run by id.

    Args:
        session: a database session
        task_run_id: the task run id

    Returns:
        orm_models.TaskRun: the task run with the flow run name
    """

    result = await session.execute(
        select(orm_models.TaskRun, orm_models.FlowRun.name.label("flow_run_name"))
        .outerjoin(
            orm_models.FlowRun, orm_models.TaskRun.flow_run_id == orm_models.FlowRun.id
        )
        .where(orm_models.TaskRun.id == task_run_id)
    )
    row = result.first()
    if not row:
        return None

    task_run = row[0]
    flow_run_name = row[1]
    if flow_run_name:
        setattr(task_run, "flow_run_name", flow_run_name)
    return task_run


async def _apply_task_run_filters(
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
    Applies filters to a task run query as a combination of EXISTS subqueries.
    """

    if task_run_filter:
        query = query.where(task_run_filter.as_sql_filter())

    # Return a simplified query in the case that the request is ONLY asking to filter on flow_run_id (and task_run_filter)
    # In this case there's no need to generate the complex EXISTS subqueries; the generated query here is much more efficient
    if (
        flow_run_filter
        and flow_run_filter.only_filters_on_id()
        and flow_run_filter.id
        and flow_run_filter.id.any_
        and not any(
            [flow_filter, deployment_filter, work_pool_filter, work_queue_filter]
        )
    ):
        query = query.where(db.TaskRun.flow_run_id.in_(flow_run_filter.id.any_))

        return query

    if (
        flow_filter
        or flow_run_filter
        or deployment_filter
        or work_pool_filter
        or work_queue_filter
    ):
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

        if work_queue_filter:
            exists_clause = exists_clause.join(
                db.WorkQueue,
                db.WorkQueue.id == db.FlowRun.work_queue_id,
            ).where(work_queue_filter.as_sql_filter())

        if work_pool_filter:
            exists_clause = exists_clause.join(
                db.WorkPool,
                sa.and_(
                    db.WorkPool.id == db.WorkQueue.work_pool_id,
                    db.WorkQueue.id == db.FlowRun.work_queue_id,
                ),
            ).where(work_pool_filter.as_sql_filter())

        query = query.where(exists_clause.exists())

    return query


@db_injector
async def read_task_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    sort: schemas.sorting.TaskRunSort = schemas.sorting.TaskRunSort.ID_DESC,
) -> Sequence[orm_models.TaskRun]:
    """
    Read task runs.

    Args:
        session: a database session
        flow_filter: only select task runs whose flows match these filters
        flow_run_filter: only select task runs whose flow runs match these filters
        task_run_filter: only select task runs that match these filters
        deployment_filter: only select task runs whose deployments match these filters
        offset: Query offset
        limit: Query limit
        sort: Query sort

    Returns:
        List[orm_models.TaskRun]: the task runs
    """

    query = select(db.TaskRun).order_by(*sort.as_sql_sort())

    query = await _apply_task_run_filters(
        db,
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

    logger.debug(f"In read_task_runs, query generated is:\n{query}")
    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def count_task_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
) -> int:
    """
    Count task runs.

    Args:
        session: a database session
        flow_filter: only count task runs whose flows match these filters
        flow_run_filter: only count task runs whose flow runs match these filters
        task_run_filter: only count task runs that match these filters
        deployment_filter: only count task runs whose deployments match these filters
    Returns:
        int: count of task runs
    """

    query = select(sa.func.count(None)).select_from(db.TaskRun)

    query = await _apply_task_run_filters(
        db,
        query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


@db_injector
async def count_task_runs_by_state(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_filter: Optional[schemas.filters.FlowFilter] = None,
    flow_run_filter: Optional[schemas.filters.FlowRunFilter] = None,
    task_run_filter: Optional[schemas.filters.TaskRunFilter] = None,
    deployment_filter: Optional[schemas.filters.DeploymentFilter] = None,
) -> schemas.states.CountByState:
    """
    Count task runs by state.

    Args:
        session: a database session
        flow_filter: only count task runs whose flows match these filters
        flow_run_filter: only count task runs whose flow runs match these filters
        task_run_filter: only count task runs that match these filters
        deployment_filter: only count task runs whose deployments match these filters
    Returns:
        schemas.states.CountByState: count of task runs by state
    """

    base_query = (
        select(db.TaskRun.state_type, sa.func.count(None).label("count"))
        .select_from(db.TaskRun)
        .group_by(db.TaskRun.state_type)
    )

    query = await _apply_task_run_filters(
        db,
        base_query,
        flow_filter=flow_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
    )

    result = await session.execute(query)

    counts = schemas.states.CountByState()

    for row in result:
        setattr(counts, row.state_type, row.count)

    return counts


@db_injector
async def delete_task_run(
    db: PrefectDBInterface, session: AsyncSession, task_run_id: UUID
) -> bool:
    """
    Delete a task run by id.

    Args:
        session: a database session
        task_run_id: the task run id to delete

    Returns:
        bool: whether or not the task run was deleted
    """

    result = await session.execute(
        delete(db.TaskRun).where(db.TaskRun.id == task_run_id)
    )
    return result.rowcount > 0


async def set_task_run_state(
    session: AsyncSession,
    task_run_id: UUID,
    state: schemas.states.State,
    force: bool = False,
    task_policy: Optional[Type[TaskRunOrchestrationPolicy]] = None,
    orchestration_parameters: Optional[Dict[str, Any]] = None,
) -> OrchestrationResult:
    """
    Creates a new orchestrated task run state.

    Setting a new state on a run is the one of the principal actions that is governed by
    Prefect's orchestration logic. Setting a new run state will not guarantee creation,
    but instead trigger orchestration rules to govern the proposed `state` input. If
    the state is considered valid, it will be written to the database. Otherwise, a
    it's possible a different state, or no state, will be created. A `force` flag is
    supplied to bypass a subset of orchestration logic.

    Args:
        session: a database session
        task_run_id: the task run id
        state: a task run state model
        force: if False, orchestration rules will be applied that may alter or prevent
            the state transition. If True, orchestration rules are not applied.

    Returns:
        OrchestrationResult object
    """

    # load the task run
    run = await models.task_runs.read_task_run(session=session, task_run_id=task_run_id)

    if not run:
        raise ObjectNotFoundError(f"Task run with id {task_run_id} not found")

    initial_state = run.state.as_state() if run.state else None
    initial_state_type = initial_state.type if initial_state else None
    proposed_state_type = state.type if state else None
    intended_transition = (initial_state_type, proposed_state_type)

    if state.state_details.deferred:
        task_policy = BackgroundTaskPolicy  # CoreTaskPolicy + prevent `Running` -> `Running` transition
    elif force or task_policy is None:
        task_policy = MinimalTaskPolicy

    orchestration_rules = task_policy.compile_transition_rules(*intended_transition)  # type: ignore
    global_rules = GlobalTaskPolicy.compile_transition_rules(*intended_transition)

    context = TaskOrchestrationContext(
        session=session,
        run=run,
        initial_state=initial_state,
        proposed_state=state,
    )

    if orchestration_parameters is not None:
        context.parameters = orchestration_parameters

    # apply orchestration rules and create the new task run state
    async with contextlib.AsyncExitStack() as stack:
        for rule in orchestration_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        for rule in global_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        await context.validate_proposed_state()

    if context.orchestration_error is not None:
        raise context.orchestration_error

    result = OrchestrationResult(
        state=context.validated_state,
        status=context.response_status,
        details=context.response_details,
    )

    return result


async def with_system_labels_for_task_run(
    session: AsyncSession,
    task_run: schemas.core.TaskRun,
) -> schemas.core.KeyValueLabels:
    """Augment user supplied labels with system default labels for a task
    run."""

    client_supplied_labels = task_run.labels or {}
    default_labels = cast(schemas.core.KeyValueLabels, {})
    parent_labels: schemas.core.KeyValueLabels = {}

    if task_run.flow_run_id:
        default_labels["prefect.flow-run.id"] = str(task_run.flow_run_id)
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=task_run.flow_run_id
        )
        parent_labels = flow_run.labels if flow_run and flow_run.labels else {}

    return parent_labels | default_labels | client_supplied_labels
