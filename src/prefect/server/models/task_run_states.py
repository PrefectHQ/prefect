"""
Functions for interacting with task run state ORM objects.
Intended for internal use by the Prefect REST API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.server.database import orm_models


async def read_task_run_state(session: sa.orm.Session, task_run_state_id: UUID):
    """
    Reads a task run state by id.

    Args:
        session: A database session
        task_run_state_id: a task run state id

    Returns:
        orm_models.TaskRunState: the task state
    """

    return await session.get(orm_models.TaskRunState, task_run_state_id)


async def read_task_run_states(session: sa.orm.Session, task_run_id: UUID):
    """
    Reads task runs states for a task run.

    Args:
        session: A database session
        task_run_id: the task run id

    Returns:
        List[orm_models.TaskRunState]: the task run states
    """

    query = (
        select(orm_models.TaskRunState)
        .filter_by(task_run_id=task_run_id)
        .order_by(orm_models.TaskRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_task_run_state(
    session: sa.orm.Session, task_run_state_id: UUID
) -> bool:
    """
    Delete a task run state by id.

    Args:
        session: A database session
        task_run_state_id: a task run state id

    Returns:
        bool: whether or not the task run state was deleted
    """

    result = await session.execute(
        delete(orm_models.TaskRunState).where(
            orm_models.TaskRunState.id == task_run_state_id
        )
    )
    return result.rowcount > 0
