"""
Functions for interacting with flow run notification policy ORM objects.
Intended for internal use by the Prefect REST API.
"""

import textwrap
from typing import Optional, Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database import PrefectDBInterface, db_injector, orm_models

DEFAULT_MESSAGE_TEMPLATE = textwrap.dedent(
    """
    Flow run {flow_name}/{flow_run_name} entered state `{flow_run_state_name}` at {flow_run_state_timestamp}.

    Flow ID: {flow_id}
    Flow run ID: {flow_run_id}
    Flow run URL: {flow_run_url}
    State message: {flow_run_state_message}
    """
)


@db_injector
async def create_flow_run_notification_policy(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_notification_policy: schemas.core.FlowRunNotificationPolicy,
) -> orm_models.FlowRunNotificationPolicy:
    """
    Creates a FlowRunNotificationPolicy.

    Args:
        session (AsyncSession): a database session
        flow_run_notification_policy (schemas.core.FlowRunNotificationPolicy): a FlowRunNotificationPolicy model

    Returns:
        orm_models.FlowRunNotificationPolicy: the newly-created FlowRunNotificationPolicy

    """
    model = db.FlowRunNotificationPolicy(**flow_run_notification_policy.model_dump())
    session.add(model)
    await session.flush()

    return model


@db_injector
async def read_flow_run_notification_policy(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_notification_policy_id: UUID,
) -> Union[orm_models.FlowRunNotificationPolicy, None]:
    """
    Reads a FlowRunNotificationPolicy by id.

    Args:
        session (AsyncSession): A database session
        flow_run_notification_policy_id (str): a FlowRunNotificationPolicy id

    Returns:
        db.FlowRunNotificationPolicy: the FlowRunNotificationPolicy
    """

    return await session.get(
        db.FlowRunNotificationPolicy, flow_run_notification_policy_id
    )


@db_injector
async def read_flow_run_notification_policies(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_notification_policy_filter: Optional[
        schemas.filters.FlowRunNotificationPolicyFilter
    ] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.FlowRunNotificationPolicy]:
    """
    Read notification policies.

    Args:
        session (AsyncSession): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db.FlowRunNotificationPolicy]: Notification policies
    """

    query = select(db.FlowRunNotificationPolicy).order_by(
        db.FlowRunNotificationPolicy.id
    )

    if flow_run_notification_policy_filter:
        query = query.where(flow_run_notification_policy_filter.as_sql_filter())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def update_flow_run_notification_policy(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_notification_policy_id: UUID,
    flow_run_notification_policy: schemas.actions.FlowRunNotificationPolicyUpdate,
) -> bool:
    """
    Update a FlowRunNotificationPolicy by id.

    Args:
        session (AsyncSession): A database session
        flow_run_notification_policy: the flow run notification policy data
        flow_run_notification_policy_id (str): a FlowRunNotificationPolicy id

    Returns:
        bool: whether or not the FlowRunNotificationPolicy was updated
    """
    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = flow_run_notification_policy.model_dump_for_orm(exclude_unset=True)

    update_stmt = (
        sa.update(db.FlowRunNotificationPolicy)
        .where(db.FlowRunNotificationPolicy.id == flow_run_notification_policy_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@db_injector
async def delete_flow_run_notification_policy(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_notification_policy_id: UUID,
) -> bool:
    """
    Delete a FlowRunNotificationPolicy by id.

    Args:
        session (AsyncSession): A database session
        flow_run_notification_policy_id (str): a FlowRunNotificationPolicy id

    Returns:
        bool: whether or not the FlowRunNotificationPolicy was deleted
    """

    result = await session.execute(
        delete(db.FlowRunNotificationPolicy).where(
            db.FlowRunNotificationPolicy.id == flow_run_notification_policy_id
        )
    )
    return result.rowcount > 0


@db_injector
async def queue_flow_run_notifications(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run: Union[schemas.core.FlowRun, orm_models.FlowRun],
) -> None:
    await db.queries.queue_flow_run_notifications(session=session, flow_run=flow_run)
