import datetime
import pendulum
from uuid import UUID
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy import select, delete
from sqlalchemy.sql.functions import mode

from prefect.orion.models import orm
from prefect.orion import schemas, models
from prefect.orion.schemas import states


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

    from_state = run.state.as_state() if run.state else None

    # --- apply retry logic
    if apply_orchestration_rules:
        if (
            from_state
            and from_state.type == states.StateType.RUNNING
            and state.type == states.StateType.FAILED
            and run.state.run_details.run_count <= run.empirical_policy.max_retries
        ):
            state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run.empirical_policy.retry_delay_seconds
                ),
                message=state.message,
                data=state.data,
            )

        if state.type == states.StateType.RUNNING and state.state_details.cache_key:
            # Check for cached states matching the cache key
            cached_state = await get_cached_task_run_state(
                session, state.state_details.cache_key
            )
            if cached_state:
                state = cached_state.as_state().copy()
                state.name = "Cached"

    # update the state details
    state.run_details = states.update_run_details(from_state=from_state, to_state=state)
    state.state_details.flow_run_id = run.flow_run_id
    state.state_details.task_run_id = task_run_id

    # create the new task run state
    new_task_run_state = orm.TaskRunState(
        task_run_id=task_run_id,
        **state.dict(shallow=True),
    )
    session.add(new_task_run_state)
    await session.flush()

    # Add the new task state to the cache if a key was provided
    if state.type == states.StateType.COMPLETED and state.state_details.cache_key:
        await cache_task_run_state(session, new_task_run_state)

    # update the ORM model state
    if run is not None:
        run.state = new_task_run_state

    return new_task_run_state


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
