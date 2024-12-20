"""
Functions for interacting with flow run state ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Sequence, Union
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def read_flow_run_state(
    db: PrefectDBInterface, session: AsyncSession, flow_run_state_id: UUID
) -> Union[orm_models.FlowRunState, None]:
    """
    Reads a flow run state by id.

    Args:
        session: A database session
        flow_run_state_id: a flow run state id

    Returns:
        orm_models.FlowRunState: the flow state
    """

    return await session.get(db.FlowRunState, flow_run_state_id)


@db_injector
async def read_flow_run_states(
    db: PrefectDBInterface, session: AsyncSession, flow_run_id: UUID
) -> Sequence[orm_models.FlowRunState]:
    """
    Reads flow runs states for a flow run.

    Args:
        session: A database session
        flow_run_id: the flow run id

    Returns:
        List[orm_models.FlowRunState]: the flow run states
    """

    query = (
        select(db.FlowRunState)
        .filter_by(flow_run_id=flow_run_id)
        .order_by(db.FlowRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def delete_flow_run_state(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_state_id: UUID,
) -> bool:
    """
    Delete a flow run state by id.

    Args:
        session: A database session
        flow_run_state_id: a flow run state id

    Returns:
        bool: whether or not the flow run state was deleted
    """

    result = await session.execute(
        delete(db.FlowRunState).where(db.FlowRunState.id == flow_run_state_id)
    )
    return result.rowcount > 0
