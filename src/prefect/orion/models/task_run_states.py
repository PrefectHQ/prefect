"""
Functions for interacting with task run state ORM objects.
Intended for internal use by the Orion API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def read_task_run_state(
    session: sa.orm.Session, task_run_state_id: UUID, db: OrionDBInterface
):
    """
    Reads a task run state by id.

    Args:
        session: A database session
        task_run_state_id: a task run state id

    Returns:
        db.TaskRunState: the task state
    """

    return await session.get(db.TaskRunState, task_run_state_id)


@inject_db
async def read_task_run_states(
    session: sa.orm.Session, task_run_id: UUID, db: OrionDBInterface
):
    """
    Reads task runs states for a task run.

    Args:
        session: A database session
        task_run_id: the task run id

    Returns:
        List[db.TaskRunState]: the task run states
    """

    query = (
        select(db.TaskRunState)
        .filter_by(task_run_id=task_run_id)
        .order_by(db.TaskRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def delete_task_run_state(
    session: sa.orm.Session, task_run_state_id: UUID, db: OrionDBInterface
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
        delete(db.TaskRunState).where(db.TaskRunState.id == task_run_state_id)
    )
    return result.rowcount > 0
