"""
Functions for interacting with flow run ORM objects.
Intended for internal use by the Orion API.
"""

import contextlib
import datetime
from itertools import chain
from typing import List, Optional
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.orchestration.core_policy import MinimalFlowPolicy
from prefect.orion.orchestration.global_policy import GlobalFlowPolicy
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    FlowOrchestrationContext,
    OrchestrationResult,
)
from prefect.orion.schemas.core import TaskRunResult
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.schemas.states import State
from prefect.orion.utilities.schemas import PrefectBaseModel


@inject_db
async def create_flow_run(
    session: AsyncSession, flow_run: schemas.core.FlowRun, db: OrionDBInterface
):
    """Creates a new flow run.

    If the provided flow run has a state attached, it will also be created.

    Args:
        session: a database session
        flow_run: a flow run model

    Returns:
        db.FlowRun: the newly-created flow run
    """
    now = pendulum.now("UTC")

    flow_run_dict = dict(
        **flow_run.dict(
            shallow=True,
            exclude={
                "created",
                "state",
                "estimated_run_time",
                "estimated_start_time_delta",
            },
            exclude_unset=True,
        ),
        created=now,
    )

    # if no idempotency key was provided, create the run directly
    if not flow_run.idempotency_key:
        model = db.FlowRun(**flow_run_dict)
        session.add(model)
        await session.flush()

    # otherwise let the database take care of enforcing idempotency
    else:
        insert_stmt = (
            (await db.insert(db.FlowRun))
            .values(**flow_run_dict)
            .on_conflict_do_nothing(
                index_elements=db.flow_run_unique_upsert_columns,
            )
        )
        await session.execute(insert_stmt)

        # read the run to see if idempotency was applied or not
        query = (
            sa.select(db.FlowRun)
            .where(
                sa.and_(
                    db.FlowRun.flow_id == flow_run.flow_id,
                    db.FlowRun.idempotency_key == flow_run.idempotency_key,
                )
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await session.execute(query)
        model = result.scalar()

    # if the flow run was created in this function call then we need to set the
    # state. If it was created idempotently, the created time won't match.
    if model.created == now and flow_run.state:
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=model.id,
            state=flow_run.state,
            force=True,
        )
    return model


@inject_db
async def update_flow_run(
    session: AsyncSession,
    flow_run_id: UUID,
    flow_run: schemas.actions.FlowRunUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Updates a flow run.

    Args:
        session: a database session
        flow_run_id: the flow run id to update
        flow_run: a flow run model

    Returns:
        bool: whether or not matching rows were found to update
    """
    update_stmt = (
        sa.update(db.FlowRun).where(db.FlowRun.id == flow_run_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow_run.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def read_flow_run(session: AsyncSession, flow_run_id: UUID, db: OrionDBInterface):
    """
    Reads a flow run by id.

    Args:
        session: A database session
        flow_run_id: a flow run id

    Returns:
        db.FlowRun: the flow run
    """

    return await session.get(db.FlowRun, flow_run_id)


@inject_db
async def _apply_flow_run_filters(
    query,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
):
    """
    Applies filters to a flow run query as a combination of EXISTS subqueries.
    """

    if flow_run_filter:
        query = query.where(flow_run_filter.as_sql_filter(db))

    if deployment_filter:
        exists_clause = select(db.Deployment).where(
            db.Deployment.id == db.FlowRun.deployment_id,
            deployment_filter.as_sql_filter(db),
        )
        query = query.where(exists_clause.exists())

    if flow_filter or task_run_filter:

        if flow_filter:
            exists_clause = select(db.Flow).where(
                db.Flow.id == db.FlowRun.flow_id,
                flow_filter.as_sql_filter(db),
            )

        if task_run_filter:
            if not flow_filter:
                exists_clause = select(db.TaskRun).where(
                    db.TaskRun.flow_run_id == db.FlowRun.id
                )
            else:
                exists_clause = exists_clause.join(
                    db.TaskRun,
                    db.TaskRun.flow_run_id == db.FlowRun.id,
                )
            exists_clause = exists_clause.where(
                db.FlowRun.id == db.TaskRun.flow_run_id,
                task_run_filter.as_sql_filter(db),
            )

        query = query.where(exists_clause.exists())

    return query


@inject_db
async def read_flow_runs(
    session: AsyncSession,
    db: OrionDBInterface,
    columns: List = None,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
    offset: int = None,
    limit: int = None,
    sort: schemas.sorting.FlowRunSort = schemas.sorting.FlowRunSort.ID_DESC,
):
    """
    Read flow runs.

    Args:
        session: a database session
        columns: a list of the flow run ORM columns to load, for performance
        flow_filter: only select flow runs whose flows match these filters
        flow_run_filter: only select flow runs match these filters
        task_run_filter: only select flow runs whose task runs match these filters
        deployment_filter: only sleect flow runs whose deployments match these filters
        offset: Query offset
        limit: Query limit
        sort: Query sort

    Returns:
        List[db.FlowRun]: flow runs
    """
    query = select(db.FlowRun).order_by(sort.as_sql_sort(db))

    if columns:
        query = query.options(load_only(*columns))

    query = await _apply_flow_run_filters(
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


class DependencyResult(PrefectBaseModel):
    id: UUID
    upstream_dependencies: List[TaskRunResult]
    state: State
    expected_start_time: Optional[datetime.datetime]
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    total_run_time: Optional[datetime.timedelta]
    estimated_run_time: Optional[datetime.timedelta]
    untrackable_result: bool


async def read_task_run_dependencies(
    session: AsyncSession,
    flow_run_id: UUID,
) -> List[DependencyResult]:
    """
    Get a task run dependency map for a given flow run.
    """
    flow_run = await models.flow_runs.read_flow_run(
        session=session, flow_run_id=flow_run_id
    )
    if not flow_run:
        raise ObjectNotFoundError(f"Flow run with id {flow_run_id} not found")

    task_runs = await models.task_runs.read_task_runs(
        session=session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            id=schemas.filters.FlowRunFilterId(any_=[flow_run_id])
        ),
    )

    dependency_graph = []

    for task_run in task_runs:
        inputs = list(set(chain(*task_run.task_inputs.values())))
        untrackable_result_status = (
            False
            if task_run.state is None
            else task_run.state.state_details.untrackable_result
        )
        dependency_graph.append(
            {
                "id": task_run.id,
                "upstream_dependencies": inputs,
                "state": task_run.state,
                "expected_start_time": task_run.expected_start_time,
                "start_time": task_run.start_time,
                "end_time": task_run.end_time,
                "total_run_time": task_run.total_run_time,
                "estimated_run_time": task_run.estimated_run_time,
                "untrackable_result": untrackable_result_status,
            }
        )

    return dependency_graph


@inject_db
async def count_flow_runs(
    session: AsyncSession,
    db: OrionDBInterface,
    flow_filter: schemas.filters.FlowFilter = None,
    flow_run_filter: schemas.filters.FlowRunFilter = None,
    task_run_filter: schemas.filters.TaskRunFilter = None,
    deployment_filter: schemas.filters.DeploymentFilter = None,
) -> int:
    """
    Count flow runs.

    Args:
        session: a database session
        flow_filter: only count flow runs whose flows match these filters
        flow_run_filter: only count flow runs that match these filters
        task_run_filter: only count flow runs whose task runs match these filters
        deployment_filter: only count flow runs whose deployments match these filters

    Returns:
        int: count of flow runs
    """

    query = select(sa.func.count(sa.text("*"))).select_from(db.FlowRun)

    query = await _apply_flow_run_filters(
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
async def delete_flow_run(
    session: AsyncSession, flow_run_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a flow run by flow_run_id.

    Args:
        session: A database session
        flow_run_id: a flow run id

    Returns:
        bool: whether or not the flow run was deleted
    """

    result = await session.execute(
        delete(db.FlowRun).where(db.FlowRun.id == flow_run_id)
    )
    return result.rowcount > 0


async def set_flow_run_state(
    session: AsyncSession,
    flow_run_id: UUID,
    state: schemas.states.State,
    force: bool = False,
    flow_policy: BaseOrchestrationPolicy = None,
) -> OrchestrationResult:
    """
    Creates a new orchestrated flow run state.

    Setting a new state on a run is the one of the principal actions that is governed by
    Orion's orchestration logic. Setting a new run state will not guarantee creation,
    but instead trigger orchestration rules to govern the proposed `state` input. If
    the state is considered valid, it will be written to the database. Otherwise, a
    it's possible a different state, or no state, will be created. A `force` flag is
    supplied to bypass a subset of orchestration logic.

    Args:
        session: a database session
        flow_run_id: the flow run id
        state: a flow run state model
        force: if False, orchestration rules will be applied that may alter or prevent
            the state transition. If True, orchestration rules are not applied.

    Returns:
        OrchestrationResult object
    """

    # load the flow run
    run = await models.flow_runs.read_flow_run(
        session=session,
        flow_run_id=flow_run_id,
    )

    if not run:
        raise ObjectNotFoundError(f"Flow run with id {flow_run_id} not found")

    initial_state = run.state.as_state() if run.state else None
    initial_state_type = initial_state.type if initial_state else None
    proposed_state_type = state.type if state else None
    intended_transition = (initial_state_type, proposed_state_type)

    if force or flow_policy is None:
        flow_policy = MinimalFlowPolicy

    orchestration_rules = flow_policy.compile_transition_rules(*intended_transition)
    global_rules = GlobalFlowPolicy.compile_transition_rules(*intended_transition)

    context = FlowOrchestrationContext(
        session=session,
        run=run,
        initial_state=initial_state,
        proposed_state=state,
    )

    # apply orchestration rules and create the new flow run state
    async with contextlib.AsyncExitStack() as stack:
        for rule in orchestration_rules:
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        for rule in global_rules:
            context = await stack.enter_async_context(rule(context))

        await context.validate_proposed_state()

    if context.orchestration_error is not None:
        raise context.orchestration_error

    result = OrchestrationResult(
        state=context.validated_state,
        status=context.response_status,
        details=context.response_details,
    )

    # if a new state is being set (either ACCEPTED from user or REJECTED
    # and set by the server), check for any notification policies
    if result.status in (SetStateStatus.ACCEPT, SetStateStatus.REJECT):
        await models.flow_run_notification_policies.queue_flow_run_notifications(
            session=session, flow_run=run
        )

    return result
