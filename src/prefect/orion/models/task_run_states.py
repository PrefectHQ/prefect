import contextlib
import datetime
import pendulum
import sqlalchemy as sa
from sqlalchemy import select, delete
from sqlalchemy.sql.functions import mode
from typing import List, Optional
from uuid import UUID

from prefect.orion import schemas, models
from prefect.orion.models import orm
from prefect.orion.schemas import states


@contextlib.asynccontextmanager
async def cache_insertion(context):
    yield context
    # Add the new task state to the cache if a key was provided
    if context['proposed_state'].type == states.StateType.COMPLETED and context['proposed_state'].state_details.cache_key:
        await cache_task_run_state(context['session'], context['validated_state'])


@contextlib.asynccontextmanager
async def retry_attempted_failures(context):
    if (
        context['initial_state']
        and context['initial_state'].type == states.StateType.RUNNING
        and context['proposed_state'].type == states.StateType.FAILED
        and context['run'].state.run_details.run_count <= context['run'].empirical_policy.max_retries
    ):
        context['proposed_state'] = states.AwaitingRetry(
            scheduled_time=pendulum.now("UTC").add(
                seconds=context['run'].empirical_policy.retry_delay_seconds
            ),
            message=context['proposed_state'].message,
            data=context['proposed_state'].data,
        )
    yield context


@contextlib.asynccontextmanager
async def cache_retrieval(context):
    if context['proposed_state'].type == states.StateType.RUNNING and context['proposed_state'].state_details.cache_key:
        # Check for cached states matching the cache key
        cached_state = await get_cached_task_run_state(
            context['session'], context['proposed_state'].state_details.cache_key
        )
        if cached_state:
            context['proposed_state'] = cached_state.as_state().copy()
            context['proposed_state'].name = "Cached"
    yield context


@contextlib.asynccontextmanager
async def update_run_details(context):
    context['proposed_state'].run_details = states.update_run_details(from_state=context['initial_state'], to_state=context['proposed_state'])
    yield context


@contextlib.asynccontextmanager
async def update_state_details(context):
    context['proposed_state'].state_details.flow_run_id = context['run'].flow_run_id
    context['proposed_state'].state_details.task_run_id = context['task_run_id']
    yield context


async def create_task_run_state(
    session: sa.orm.Session,
    task_run_id: UUID,
    state: schemas.actions.StateCreate,
    apply_orchestration_rules: bool = True,
) -> orm.TaskRunState:
    """Creates a new task run state

    Args:
        session (sa.orm.Session): a database session
        task_run_id (str): the task run id
        state (schemas.actions.StateCreate): a task run state model

    Returns:
        orm.TaskRunState: the newly-created task run state
    """

    # load the task run
    run = await models.task_runs.read_task_run(
        session=session,
        task_run_id=task_run_id,
    )

    if not run:
        raise ValueError(f"Invalid task run: {task_run_id}")

    initial_state = run.state.as_state() if run.state else None

    if apply_orchestration_rules:
        orchestration_rules = [retry_attempted_failures, cache_retrieval, cache_insertion]
    else:
        orchestration_rules = []

    global_rules = [update_run_details, update_state_details]

    # create the new task run state
    async with contextlib.AsyncExitStack() as stack:
        context = {'initial_state': initial_state, 'proposed_state': state, 'run': run, 'session': session, 'task_run_id': task_run_id}

        for rule in orchestration_rules:
            context = await stack.enter_async_context(rule(context))

        for rule in global_rules:
            context = await stack.enter_async_context(rule(context))

        validated_state = orm.TaskRunState(
            task_run_id=context['task_run_id'],
            **context['proposed_state'].dict(shallow=True),
        )
        session.add(validated_state)
        context['validated_state'] = validated_state
        await session.flush()
        await stack.aclose()

    # update the ORM model state
    if run is not None:
        run.state = validated_state

    return validated_state


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
        .filter(orm.TaskRunState.task_run_id == task_run_id)
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


async def get_cached_task_run_state(
    session: sa.orm.Session, cache_key: str
) -> Optional[orm.TaskRunState]:
    task_run_state_id = (
        select(orm.TaskRunStateCache.task_run_state_id)
        .filter(
            sa.and_(
                orm.TaskRunStateCache.cache_key == cache_key,
                sa.or_(
                    orm.TaskRunStateCache.cache_expiration.is_(None),
                    orm.TaskRunStateCache.cache_expiration > pendulum.now("utc"),
                ),
            ),
        )
        .order_by(orm.TaskRunStateCache.created.desc())
        .limit(1)
    ).scalar_subquery()
    query = select(orm.TaskRunState).filter(orm.TaskRunState.id == task_run_state_id)
    result = await session.execute(query)
    return result.scalar()


async def cache_task_run_state(
    session: sa.orm.Session, state: orm.TaskRunState
) -> None:
    # create the new task run state
    new_cache_item = orm.TaskRunStateCache(
        cache_key=state.state_details.cache_key,
        cache_expiration=state.state_details.cache_expiration,
        task_run_state_id=state.id,
    )
    session.add(new_cache_item)
    await session.flush()
