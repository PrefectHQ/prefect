"""
Functions for interacting with agent ORM objects.
Intended for internal use by the Orion API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_agent(
    session: sa.orm.Session,
    agent: schemas.core.Agent,
    db: OrionDBInterface,
):
    """
    Inserts a Agent.

    If a Agent with the same name exists, an error will be thrown.

    Args:
        session (sa.orm.Session): a database session
        agent (schemas.core.Agent): a Agent model

    Returns:
        db.Agent: the newly-created or updated Agent

    """

    model = db.Agent(**agent.dict())
    session.add(model)
    await session.flush()

    return model


@inject_db
async def read_agent(session: sa.orm.Session, agent_id: UUID, db: OrionDBInterface):
    """
    Reads a Agent by id.

    Args:
        session (sa.orm.Session): A database session
        agent_id (str): a Agent id

    Returns:
        db.Agent: the Agent
    """

    return await session.get(db.Agent, agent_id)


@inject_db
async def read_agents(
    db: OrionDBInterface,
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
):
    """
    Read Agents.

    Args:
        session (sa.orm.Session): A database session
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


@inject_db
async def update_agent(
    session: sa.orm.Session,
    agent_id: UUID,
    agent: schemas.core.Agent,
    db: OrionDBInterface,
) -> bool:
    """
    Update a Agent by id.

    Args:
        session (sa.orm.Session): A database session
        agent: the work queue data
        agent_id (str): a Agent id

    Returns:
        bool: whether or not the Agent was deleted
    """

    update_stmt = (
        sa.update(db.Agent).where(db.Agent.id == agent_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**agent.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_agent(
    session: sa.orm.Session, agent_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a Agent by id.

    Args:
        session (sa.orm.Session): A database session
        agent_id (str): a Agent id

    Returns:
        bool: whether or not the Agent was deleted
    """

    result = await session.execute(delete(db.Agent).where(db.Agent.id == agent_id))
    return result.rowcount > 0
