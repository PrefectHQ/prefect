import contextlib
from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import models, schemas
from prefect.orion.models import orm
from prefect.orion.orchestration.core_policy import CoreTaskPolicy
from prefect.orion.orchestration.global_policy import GlobalPolicy
from prefect.orion.orchestration.rules import (
    TaskOrchestrationContext,
    OrchestrationResult,
)


async def orchestrate_task_run_state(
    session: sa.orm.Session,
    task_run_id: UUID,
    state: schemas.states.State,
    apply_orchestration_rules: bool = True,
) -> orm.TaskRunState:
    """Creates a new task run state

    Args:
        session (sa.orm.Session): a database session
        task_run_id (str): the task run id
        state (schemas.states.State): a task run state model

    Returns:
        orm.TaskRunState: the newly-created task run state
    """

    # load the task run
    run = await models.task_runs.read_task_run(session=session, task_run_id=task_run_id)

    if not run:
        raise ValueError(f"Invalid task run: {task_run_id}")

    initial_state = run.state.as_state() if run.state else None
    initial_state_type = initial_state.type if initial_state else None
    proposed_state_type = state.type if state else None
    intended_transition = (initial_state_type, proposed_state_type)

    if apply_orchestration_rules:
        orchestration_rules = CoreTaskPolicy.compile_transition_rules(
            *intended_transition
        )
    else:
        orchestration_rules = []

    global_rules = GlobalPolicy.compile_transition_rules(*intended_transition)

    context = TaskOrchestrationContext(
        initial_state=initial_state,
        proposed_state=state,
        session=session,
        run=run,
        run_id=task_run_id,
    )

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

        validated_orm_state = await context.validate_proposed_state()

        if validated_orm_state is not None:
            run.set_state(validated_orm_state)
            await session.flush()

    result = OrchestrationResult(
        state=validated_orm_state,
        status=context.response_status,
        details=context.response_details,
    )

    return result


async def read_task_run_state(
    session: sa.orm.Session, task_run_state_id: UUID
) -> orm.TaskRunState:
    """Reads a task run state by id

    Args:
        session (sa.orm.Session): A database session
        task_run_state_id (str): a task run state id

    Returns:
        orm.TaskRunState: the task state
    """
    return await session.get(orm.TaskRunState, task_run_state_id)


async def read_task_run_states(
    session: sa.orm.Session, task_run_id: UUID
) -> List[orm.TaskRunState]:
    """Reads task runs states for a task run

    Args:
        session (sa.orm.Session): A database session
        task_run_id (str): the task run id

    Returns:
        List[orm.TaskRunState]: the task run states
    """
    query = (
        select(orm.TaskRunState)
        .filter_by(task_run_id=task_run_id)
        .order_by(orm.TaskRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_task_run_state(
    session: sa.orm.Session, task_run_state_id: UUID
) -> bool:
    """Delete a task run state by id

    Args:
        session (sa.orm.Session): A database session
        task_run_state_id (str): a task run state id

    Returns:
        bool: whether or not the task run state was deleted
    """
    result = await session.execute(
        delete(orm.TaskRunState).where(orm.TaskRunState.id == task_run_state_id)
    )
    return result.rowcount > 0
