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
from prefect.orion.utilities.database import UUID as UUIDTypeDecorator
from prefect.orion.utilities.database import json_has_any_key

DEFAULT_MESSAGE_TEMPLATE = textwrap.dedent(
    """
    Flow run {flow_name}/{flow_run_name} entered state `{flow_run_state_name}` at {flow_run_state_timestamp}.

    Flow ID: {flow_id}
    Flow run ID: {flow_run_id}
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
    if not isinstance(
        flow_run_notification_policy, schemas.actions.FlowRunNotificationPolicyUpdate
    ):
        raise ValueError(
            "Expected parameter flow_run_notification_policy to have type "
            f"schemas.actions.FlowRunNotificationPolicyUpdate, got {type(flow_run_notification_policy)!r} instead"
        )

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
    # insert a <policy, state> pair into the notification queue
    stmt = (await db.insert(db.FlowRunNotificationQueue)).from_select(
        [
            db.FlowRunNotificationQueue.flow_run_notification_policy_id,
            db.FlowRunNotificationQueue.flow_run_state_id,
        ],
        # ... by selecting from any notification policy that matches the criteria
        sa.select(
            db.FlowRunNotificationPolicy.id,
            sa.cast(sa.literal(str(flow_run.state_id)), UUIDTypeDecorator),
        )
        .select_from(db.FlowRunNotificationPolicy)
        .where(
            sa.and_(
                # the policy is active
                db.FlowRunNotificationPolicy.is_active.is_(True),
                # the policy state names aren't set or match the current state name
                sa.or_(
                    db.FlowRunNotificationPolicy.state_names == [],
                    json_has_any_key(
                        db.FlowRunNotificationPolicy.state_names, [flow_run.state_name]
                    ),
                ),
                # the policy tags aren't set, or the tags match the flow run tags
                sa.or_(
                    db.FlowRunNotificationPolicy.tags == [],
                    json_has_any_key(db.FlowRunNotificationPolicy.tags, flow_run.tags),
                ),
            )
        ),
        # don't send python defaults as part of the insert statement, because they are
        # evaluated once per statement and create unique constraint violations on each row
        include_defaults=False,
    )
    await session.execute(stmt)
