"""
Functions for interacting with flow run notification policy ORM objects.
Intended for internal use by the Orion API.
"""

import textwrap
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface

DEFAULT_MESSAGE_TEMPLATE = textwrap.dedent(
    """
    Flow run {flow_name}/{flow_run_name} entered state `{flow_run_state_name}` at {flow_run_state_timestamp}.

    Flow ID: {flow_id}
    Flow run ID: {flow_run_id}
    Flow run URL: {flow_run_url}
    State message: {flow_run_state_message}
    """
)


@inject_db
async def create_flow_run_notification_policy(
    session: sa.orm.Session,
    flow_run_notification_policy: schemas.core.FlowRunNotificationPolicy,
    db: OrionDBInterface,
):
    """
    Creates a FlowRunNotificationPolicy.

    Args:
        session (sa.orm.Session): a database session
        flow_run_notification_policy (schemas.core.FlowRunNotificationPolicy): a FlowRunNotificationPolicy model

    Returns:
        db.FlowRunNotificationPolicy: the newly-created FlowRunNotificationPolicy

    """
    model = db.FlowRunNotificationPolicy(**flow_run_notification_policy.dict())
    session.add(model)
    await session.flush()

    return model


@inject_db
async def read_flow_run_notification_policy(
    session: sa.orm.Session,
    flow_run_notification_policy_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a FlowRunNotificationPolicy by id.

    Args:
        session (sa.orm.Session): A database session
        flow_run_notification_policy_id (str): a FlowRunNotificationPolicy id

    Returns:
        db.FlowRunNotificationPolicy: the FlowRunNotificationPolicy
    """

    return await session.get(
        db.FlowRunNotificationPolicy, flow_run_notification_policy_id
    )


@inject_db
async def read_flow_run_notification_policies(
    db: OrionDBInterface,
    session: sa.orm.Session,
    flow_run_notification_policy_filter: schemas.filters.FlowRunNotificationPolicyFilter = None,
    offset: int = None,
    limit: int = None,
):
    """
    Read notification policies.

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db.FlowRunNotificationPolicy]: Notification policies
    """

    query = select(db.FlowRunNotificationPolicy).order_by(
        db.FlowRunNotificationPolicy.id
    )

    if flow_run_notification_policy_filter:
        query = query.where(flow_run_notification_policy_filter.as_sql_filter(db))

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_flow_run_notification_policy(
    session: sa.orm.Session,
    flow_run_notification_policy_id: UUID,
    flow_run_notification_policy: schemas.actions.FlowRunNotificationPolicyUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Update a FlowRunNotificationPolicy by id.

    Args:
        session (sa.orm.Session): A database session
        flow_run_notification_policy: the flow run notification policy data
        flow_run_notification_policy_id (str): a FlowRunNotificationPolicy id

    Returns:
        bool: whether or not the FlowRunNotificationPolicy was updated
    """
    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = flow_run_notification_policy.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.FlowRunNotificationPolicy)
        .where(db.FlowRunNotificationPolicy.id == flow_run_notification_policy_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_flow_run_notification_policy(
    session: sa.orm.Session, flow_run_notification_policy_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a FlowRunNotificationPolicy by id.

    Args:
        session (sa.orm.Session): A database session
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


@inject_db
async def queue_flow_run_notifications(
    session: sa.orm.session,
    flow_run: schemas.core.FlowRun,
    db: OrionDBInterface,
):
    await db.queries.queue_flow_run_notifications(
        session=session, flow_run=flow_run, db=db
    )
