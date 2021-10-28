"""
Functions for interacting with flow run state ORM objects.
Intended for internal use by the Orion API.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion.database.dependencies import inject_db_config


@inject_db_config
async def read_flow_run_state(
    session: sa.orm.Session, flow_run_state_id: UUID, db_config=None
):
    """
    Reads a flow run state by id.

    Args:
        session: A database session
        flow_run_state_id: a flow run state id

    Returns:
        db_config.FlowRunState: the flow state
    """

    return await session.get(db_config.FlowRunState, flow_run_state_id)


@inject_db_config
async def read_flow_run_states(
    session: sa.orm.Session, flow_run_id: UUID, db_config=None
):
    """
    Reads flow runs states for a flow run.

    Args:
        session: A database session
        flow_run_id: the flow run id

    Returns:
        List[db_config.FlowRunState]: the flow run states
    """

    query = (
        select(db_config.FlowRunState)
        .filter_by(flow_run_id=flow_run_id)
        .order_by(db_config.FlowRunState.timestamp)
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db_config
async def delete_flow_run_state(
    session: sa.orm.Session,
    flow_run_state_id: UUID,
    db_config=None,
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
        delete(db_config.FlowRunState).where(
            db_config.FlowRunState.id == flow_run_state_id
        )
    )
    return result.rowcount > 0
