"""
Functions for interacting with agent ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Union
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def create_agent(
    db: PrefectDBInterface,
    session: AsyncSession,
    agent: schemas.core.Agent,
):
    """
    Inserts a Agent.

    If a Agent with the same name exists, an error will be thrown.

    Args:
        session (AsyncSession): a database session
        agent (schemas.core.Agent): a Agent model

    Returns:
        db.Agent: the newly-created or updated Agent

    """

    model = db.Agent(**agent.dict())
    session.add(model)
    await session.flush()

    return model


@db_injector
async def read_agent(
    db: PrefectDBInterface,
    session: AsyncSession,
    agent_id: UUID,
):
    """
    Reads a Agent by id.

    Args:
        session (AsyncSession): A database session
        agent_id (str): a Agent id

    Returns:
        db.Agent: the Agent
    """

    return await session.get(db.Agent, agent_id)


@db_injector
async def read_agents(
    db: PrefectDBInterface,
    session: AsyncSession,
    offset: Union[int, None] = None,
    limit: Union[int, None] = None,
):
    """
    Read Agents.

    Args:
        session (AsyncSession): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db.Agent]: Agents
    """

    query = select(db.Agent).order_by(db.Agent.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def update_agent(
    db: PrefectDBInterface,
    session: AsyncSession,
    agent_id: UUID,
    agent: schemas.core.Agent,
) -> bool:
    """
    Update a Agent by id.

    Args:
        session (AsyncSession): A database session
        agent: the work queue data
        agent_id (str): a Agent id

    Returns:
        bool: whether or not the Agent was deleted
    """

    update_stmt = (
        sa.update(db.Agent)
        .where(db.Agent.id == agent_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**agent.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@db_injector
async def record_agent_poll(
    db: PrefectDBInterface,
    session: AsyncSession,
    agent_id: UUID,
    work_queue_id: UUID,
) -> None:
    """
    Record that an agent has polled a work queue.

    If the agent_id already exists, work_queue and last_activity_time
    will be updated.

    This is a convenience method for designed for speed when agents
    are polling work queues. For other operations, the
    `create_agent` and `update_agent` methods should be used.

    Args:
        session (AsyncSession): A database session
        agent_id: An agent id
        work_queue_id: A work queue id
    """
    agent_data = schemas.core.Agent(
        id=agent_id, work_queue_id=work_queue_id, last_activity_time=pendulum.now("UTC")
    )
    insert_stmt = (
        db.insert(db.Agent)
        .values(
            **agent_data.dict(
                include={"id", "name", "work_queue_id", "last_activity_time"}
            )
        )
        .on_conflict_do_update(
            index_elements=[db.Agent.id],
            set_=agent_data.dict(
                shallow=True, include={"work_queue_id", "last_activity_time"}
            ),
        )
    )
    await session.execute(insert_stmt)


@db_injector
async def delete_agent(
    db: PrefectDBInterface,
    session: AsyncSession,
    agent_id: UUID,
) -> bool:
    """
    Delete a Agent by id.

    Args:
        session (AsyncSession): A database session
        agent_id (str): a Agent id

    Returns:
        bool: whether or not the Agent was deleted
    """

    result = await session.execute(delete(db.Agent).where(db.Agent.id == agent_id))
    return result.rowcount > 0
