from uuid import UUID
from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete
from sqlalchemy.sql.functions import mode

from prefect.orion.models import orm
from prefect.orion import schemas, models
from prefect.orion.schemas.states import RunDetails


async def create_task_run_state(
    session: sa.orm.Session,
    task_run_id: UUID,
    state: schemas.actions.StateCreate,
) -> orm.TaskRunState:
    """Creates a new task run state

    Args:
        session (sa.orm.Session): a database session
        task_run_id (str): the task run id
        state (schemas.actions.StateCreate): a task run state model

    Returns:
        orm.TaskRunState: the newly-created task run state
    """
    # carry over RunDetails from the most recent state
    run = await models.task_runs.read_task_run(session=session, task_run_id=task_run_id)
    if run and run.state is not None:
        run_details = run.state.run_details
        run_details.previous_state_id = run.state.id
    else:
        run_details = RunDetails()

    # ensure task run id is accurate in state details
    state.state_details.task_run_id = task_run_id

    # create the new task run state
    new_task_run_state = orm.TaskRunState(
        **state.dict(exclude={"data", "state_details"}),
        task_run_id=task_run_id,
        run_details=run_details,
        state_details=state.state_details
    )
    session.add(new_task_run_state)
    await session.flush()

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
