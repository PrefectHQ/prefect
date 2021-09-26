import contextlib
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect
from prefect.orion import models, schemas
from prefect.orion.models import orm
from prefect.orion.orchestration.core_policy import CoreFlowPolicy
from prefect.orion.orchestration.global_policy import GlobalFlowPolicy
from prefect.orion.orchestration.rules import (
    FlowOrchestrationContext,
    OrchestrationResult,
)
from prefect.orion.utilities.database import dialect_specific_insert


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
    now = pendulum.now("UTC")
    # if there's no idempotency key, just create the run
    if not flow_run.idempotency_key:
        model = orm.FlowRun(
            **flow_run.dict(
                shallow=True,
                exclude={
                    "state",
                    "estimated_run_time",
                    "estimated_start_time_delta",
                },
            ),
            state=None,
        )
        session.add(model)
        await session.flush()

    # otherwise let the database take care of enforcing idempotency
    else:
        insert_stmt = (
            dialect_specific_insert(orm.FlowRun)
            .values(
                **flow_run.dict(shallow=True, exclude={"state"}, exclude_unset=True)
            )
            .on_conflict_do_nothing(
                index_elements=[orm.FlowRun.flow_id, orm.FlowRun.idempotency_key],
            )
        )
        await session.execute(insert_stmt)
        query = (
            sa.select(orm.FlowRun)
            .where(
                sa.and_(
                    orm.FlowRun.flow_id == flow_run.flow_id,
                    orm.FlowRun.idempotency_key == flow_run.idempotency_key,
                )
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await session.execute(query)
        model = result.scalar()

    if model.created >= now and flow_run.state:
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=model.id,
            state=flow_run.state,
            force=True,
        )
    return model


async def update_flow_run(
    session: sa.orm.Session, flow_run_id: UUID, flow_run: schemas.actions.FlowRunUpdate
) -> bool:
    """
    Updates a flow run

    Args:
        session (sa.orm.Session): a database session
        flow_run_id (UUID): the flow run id to update
        flow_run (schemas.actions.FlowRun): a flow run model

    Returns:
        bool: whether or not matching rows were found to update

    """
    if not isinstance(flow_run, schemas.actions.FlowRunUpdate):
        raise ValueError(
            f"Expected parameter flow_run to have type schemas.actions.FlowRunUpdate, got {type(flow_run)!r} instead"
        )

    update_stmt = (
        sa.update(orm.FlowRun).where(orm.FlowRun.id == flow_run_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**flow_run.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


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
    sort: schemas.sorting.FlowRunSort = schemas.sorting.FlowRunSort.ID_DESC,
) -> List[orm.FlowRun]:
    """Read flow runs

    Args:
        session (sa.orm.Session): a database session
        flow_filter (FlowFilter, optional): only select flow runs whose flows match these filters
        flow_run_filter (FlowRunFilter, optional): only select flow runs match these filters
        task_run_filter (TaskRunFilter, optional): only select flow runs whose task runs match these filters
        offset (int, optional): Query offset
        limit (int, optional): Query limit
        sort (schemas.sorting.FlowRunSort, optional) - Query sort

    Returns:
        List[orm.FlowRun]: flow runs
    """

    query = select(orm.FlowRun).order_by(sort.as_sql_sort())

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


async def set_flow_run_state(
    session: sa.orm.Session,
    flow_run_id: UUID,
    state: schemas.states.State,
    force: bool = False,
) -> orm.FlowRunState:
    """Creates a new flow run state

    Args:
        session (sa.orm.Session): a database session
        flow_run_id (str): the flow run id
        state (schemas.states.State): a flow run state model
        force (bool): if False, orchestration rules will be applied that may
            alter or prevent the state transition. If True, orchestration rules are
            not applied.

    Returns:
        orm.FlowRunState: the newly-created flow run state
    """
    # load the flow run
    run = await models.flow_runs.read_flow_run(
        session=session,
        flow_run_id=flow_run_id,
    )

    if not run:
        raise ValueError(f"Invalid flow run: {flow_run_id}")

    initial_state = run.state.as_state() if run.state else None
    initial_state_type = initial_state.type if initial_state else None
    proposed_state_type = state.type if state else None
    intended_transition = (initial_state_type, proposed_state_type)

    global_rules = GlobalFlowPolicy.compile_transition_rules(*intended_transition)

    if force:
        orchestration_rules = []
    else:
        orchestration_rules = CoreFlowPolicy.compile_transition_rules(
            *intended_transition
        )

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
            context = await stack.enter_async_context(
                rule(context, *intended_transition)
            )

        await context.validate_proposed_state()

    await session.flush()

    result = OrchestrationResult(
        state=context.validated_state,
        status=context.response_status,
        details=context.response_details,
    )

    return result
