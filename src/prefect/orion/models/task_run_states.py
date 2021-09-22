from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion.models import orm


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
