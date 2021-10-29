"""
Functions for interacting with task run state ORM objects.
Intended for internal use by the Orion API.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion.database.dependencies import inject_db_interface


@inject_db_interface
async def read_task_run_state(
    session: sa.orm.Session,
    task_run_state_id: UUID,
    db_interface=None,
):
    """
    Reads a task run state by id.

    Args:
        session: A database session
        task_run_state_id: a task run state id

    Returns:
        db_interface.TaskRunState: the task state
    """

    return await session.get(db_interface.TaskRunState, task_run_state_id)


@inject_db_interface
async def read_task_run_states(
    session: sa.orm.Session, task_run_id: UUID, db_interface=None
):
    """
    Reads task runs states for a task run.

    Args:
        session: A database session
        task_run_id: the task run id

    Returns:
        List[db_interface.TaskRunState]: the task run states
    """

    query = (
        select(db_interface.TaskRunState)
        .filter_by(task_run_id=task_run_id)
        .order_by(db_interface.TaskRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db_interface
async def delete_task_run_state(
    session: sa.orm.Session,
    task_run_state_id: UUID,
    db_interface=None,
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
        delete(db_interface.TaskRunState).where(
            db_interface.TaskRunState.id == task_run_state_id
        )
    )
    return result.rowcount > 0
