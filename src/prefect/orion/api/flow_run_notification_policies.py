"""
Routes for interacting with flow run notification policy objects.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(
    prefix="/flow_run_notification_policies", tags=["Flow Run Notification Policies"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_flow_run_notification_policy(
    flow_run_notification_policy: schemas.actions.FlowRunNotificationPolicyCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRunNotificationPolicy:
    """
    Creates a new flow run notification policy.
    """

    return (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session, flow_run_notification_policy=flow_run_notification_policy
        )
    )


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow_run_notification_policy(
    flow_run_notification_policy: schemas.actions.FlowRunNotificationPolicyUpdate,
    flow_run_notification_policy_id: UUID = Path(
        ..., description="The flow run notification policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Updates an existing flow run notification policy.
    """

    result = (
        await models.flow_run_notification_policies.update_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=flow_run_notification_policy_id,
            flow_run_notification_policy=flow_run_notification_policy,
        )
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow run notification policy {id} not found",
        )


@router.get("/{id}")
async def read_flow_run_notification_policy(
    flow_run_notification_policy_id: UUID = Path(
        ..., description="The flow run notification policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRunNotificationPolicy:
    """
    Get a flow run notification policy by id.
    """
    flow_run_notification_policy = (
        await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=flow_run_notification_policy_id,
        )
    )
    if not flow_run_notification_policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="flow run notification policy not found",
        )
    return flow_run_notification_policy


@router.post("/filter")
async def read_flow_run_notification_policies(
    limit: int = dependencies.LimitBody(),
    flow_run_notification_policy_filter: schemas.filters.FlowRunNotificationPolicyFilter = None,
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.FlowRunNotificationPolicy]:
    """
    Query for flow run notification policies.
    """
    return (
        await models.flow_run_notification_policies.read_flow_run_notification_policies(
            session=session,
            flow_run_notification_policy_filter=flow_run_notification_policy_filter,
            offset=offset,
            limit=limit,
        )
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run_notification_policy(
    flow_run_notification_policy_id: UUID = Path(
        ..., description="The flow run notification policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a flow run notification policy by id.
    """
    result = (
        await models.flow_run_notification_policies.delete_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=flow_run_notification_policy_id,
        )
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="flow run notification policy not found",
        )
