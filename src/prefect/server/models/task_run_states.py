"""
Functions for interacting with task run state ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Sequence, Union
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector, orm_models


@db_injector
async def read_task_run_state(
    db: PrefectDBInterface, session: AsyncSession, task_run_state_id: UUID
) -> Union[orm_models.TaskRunState, None]:
    """
    Reads a task run state by id.

    Args:
        session: A database session
        task_run_state_id: a task run state id

    Returns:
        orm_models.TaskRunState: the task state
    """

    return await session.get(db.TaskRunState, task_run_state_id)


@db_injector
async def read_task_run_states(
    db: PrefectDBInterface, session: AsyncSession, task_run_id: UUID
) -> Sequence[orm_models.TaskRunState]:
    """
    Reads task runs states for a task run.

    Args:
        session: A database session
        task_run_id: the task run id

    Returns:
        List[orm_models.TaskRunState]: the task run states
    """

    query = (
        select(db.TaskRunState)
        .filter_by(task_run_id=task_run_id)
        .order_by(db.TaskRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_task_run_state(
    db: PrefectDBInterface, session: AsyncSession, task_run_state_id: UUID
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
