"""
Functions for interacting with flow run alert policy ORM objects.
Intended for internal use by the Orion API.
"""

from uuid import UUID
from prefect.orion.utilities.database import json_has_any_key, UUID as UUIDTypeDecorator
import textwrap
import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface

TEMPLATE_KWARGS = [
    "flow_run_alert_policy_id",
    "flow_run_alert_policy_name",
    "flow_id",
    "flow_name",
    "flow_run_id",
    "flow_run_name",
    "flow_run_parameters",
    "flow_run_state_type",
    "flow_run_state_name",
    "flow_run_state_timestamp",
    "flow_run_state_message",
]

DEFAULT_MESSAGE_TEMPLATE = textwrap.dedent(
    """
    Flow run {flow_name}/{flow_run_name} entered state {flow_run_state_name} at {flow_run_state_timestamp}.

    Flow ID: {flow_id}
    Flow run ID: {flow_run_id}
    """
)


@inject_db
async def create_flow_run_alert_policy(
    session: sa.orm.Session,
    flow_run_alert_policy: schemas.core.FlowRunAlertPolicy,
    db: OrionDBInterface,
):
    """
    Creates a FlowRunAlertPolicy.

    Args:
        session (sa.orm.Session): a database session
        flow_run_alert_policy (schemas.core.FlowRunAlertPolicy): a FlowRunAlertPolicy model

    Returns:
        db.FlowRunAlertPolicy: the newly-created FlowRunAlertPolicy

    """
    model = db.FlowRunAlertPolicy(**flow_run_alert_policy.dict())
    session.add(model)
    await session.flush()

    return model


@inject_db
async def read_flow_run_alert_policy(
    session: sa.orm.Session,
    flow_run_alert_policy_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a FlowRunAlertPolicy by id.

    Args:
        session (sa.orm.Session): A database session
        flow_run_alert_policy_id (str): a FlowRunAlertPolicy id

    Returns:
        db.FlowRunAlertPolicy: the FlowRunAlertPolicy
    """

    return await session.get(db.FlowRunAlertPolicy, flow_run_alert_policy_id)


@inject_db
async def read_flow_run_alert_policies(
    db: OrionDBInterface,
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
):
    """
    Read WorkQueues.

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db.FlowRunAlertPolicy]: WorkQueues
    """

    query = select(db.FlowRunAlertPolicy).order_by(db.FlowRunAlertPolicy.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_flow_run_alert_policy(
    session: sa.orm.Session,
    flow_run_alert_policy_id: UUID,
    flow_run_alert_policy: schemas.actions.FlowRunAlertPolicyUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Update a FlowRunAlertPolicy by id.

    Args:
        session (sa.orm.Session): A database session
        flow_run_alert_policy: the flow run alert policy data
        flow_run_alert_policy_id (str): a FlowRunAlertPolicy id

    Returns:
        bool: whether or not the FlowRunAlertPolicy was updated
    """
    if not isinstance(flow_run_alert_policy, schemas.actions.FlowRunAlertPolicyUpdate):
        raise ValueError(
            "Expected parameter flow_run_alert_policy to have type "
            f"schemas.actions.FlowRunAlertPolicyUpdate, got {type(flow_run_alert_policy)!r} instead"
        )

    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = flow_run_alert_policy.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.FlowRunAlertPolicy)
        .where(db.FlowRunAlertPolicy.id == flow_run_alert_policy_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_flow_run_alert_policy(
    session: sa.orm.Session, flow_run_alert_policy_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a FlowRunAlertPolicy by id.

    Args:
        session (sa.orm.Session): A database session
        flow_run_alert_policy_id (str): a FlowRunAlertPolicy id

    Returns:
        bool: whether or not the FlowRunAlertPolicy was deleted
    """

    result = await session.execute(
        delete(db.FlowRunAlertPolicy).where(
            db.FlowRunAlertPolicy.id == flow_run_alert_policy_id
        )
    )
    return result.rowcount > 0


@inject_db
async def queue_flow_run_alerts(
    session: sa.orm.session,
    flow_run: schemas.core.FlowRun,
    db: OrionDBInterface,
):
    # insert a <policy, state> pair into the alert queue
    stmt = (await db.insert(db.FlowRunAlertQueue)).from_select(
        [
            db.FlowRunAlertQueue.flow_run_alert_policy_id,
            db.FlowRunAlertQueue.flow_run_state_id,
        ],
        # ... by selecting from any alert policy that matches the criteria
        sa.select(
            db.FlowRunAlertPolicy.id,
            sa.cast(sa.literal(str(flow_run.state_id)), UUIDTypeDecorator),
        )
        .select_from(db.FlowRunAlertPolicy)
        .where(
            sa.and_(
                # the policy is active
                db.FlowRunAlertPolicy.is_active.is_(True),
                # the policy state names aren't set or match the current state name
                sa.or_(
                    db.FlowRunAlertPolicy.state_names == [],
                    json_has_any_key(
                        db.FlowRunAlertPolicy.state_names, [flow_run.state_name]
                    ),
                ),
                # the policy tags aren't set, or the tags match the flow run tags
                sa.or_(
                    db.FlowRunAlertPolicy.tags == [],
                    json_has_any_key(db.FlowRunAlertPolicy.tags, flow_run.tags),
                ),
            )
        ),
        # don't send python defaults as part of the insert statement, because they are
        # evaluated once per statement and create unique constraint violations on each row
        include_defaults=False,
    )
    await session.execute(stmt)
