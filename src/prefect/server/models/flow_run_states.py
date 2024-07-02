"""
Functions for interacting with flow run state ORM objects.
Intended for internal use by the Prefect REST API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.server.database import orm_models
from prefect.server.database.interface import PrefectDBInterface


async def read_flow_run_state(
    session: sa.orm.Session, flow_run_state_id: UUID, db: PrefectDBInterface
):
    """
    Reads a flow run state by id.

    Args:
        session: A database session
        flow_run_state_id: a flow run state id

    Returns:
        db.FlowRunState: the flow state
    """

    return await session.get(orm_models.FlowRunState, flow_run_state_id)


async def read_flow_run_states(
    session: sa.orm.Session, flow_run_id: UUID, db: PrefectDBInterface
):
    """
    Reads flow runs states for a flow run.

    Args:
        session: A database session
        flow_run_id: the flow run id

    Returns:
        List[db.FlowRunState]: the flow run states
    """

    query = (
        select(orm_models.FlowRunState)
        .filter_by(flow_run_id=flow_run_id)
        .order_by(orm_models.FlowRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_flow_run_state(
    session: sa.orm.Session,
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
        delete(orm_models.FlowRunState).where(
            orm_models.FlowRunState.id == flow_run_state_id
        )
    )
    return result.rowcount > 0
