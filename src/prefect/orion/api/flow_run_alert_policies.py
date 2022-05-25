"""
Routes for interacting with flow run alert policy objects.
"""

import datetime
from typing import List, Optional
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(
    prefix="/flow_run_alert_policies", tags=["Flow Run Alert Policies"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_flow_run_alert_policy(
    flow_run_alert_policy: schemas.actions.FlowRunAlertPolicyCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRunAlertPolicy:
    """
    Creates a new flow run alert policy.
    """

    return await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session, flow_run_alert_policy=flow_run_alert_policy
    )


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow_run_alert(
    flow_run_alert_policy: schemas.actions.FlowRunAlertPolicyUpdate,
    flow_run_alert_policy_id: UUID = Path(
        ..., description="The flow run alert policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Updates an existing flow run alert policy.
    """

    result = await models.flow_run_alert_policies.update_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy_id=flow_run_alert_policy_id,
        flow_run_alert_policy=flow_run_alert_policy,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow run alert policy {id} not found",
        )


@router.get("/{id}")
async def read_flow_run_alert_policy(
    flow_run_alert_policy_id: UUID = Path(
        ..., description="The flow run alert policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRunAlertPolicy:
    """
    Get a flow run alert policy by id.
    """
    flow_run_alert_policy = (
        await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=flow_run_alert_policy_id
        )
    )
    if not flow_run_alert_policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="flow run alert policy not found",
        )
    return flow_run_alert_policy


@router.post("/filter")
async def read_flow_run_alert_policies(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.FlowRunAlertPolicy]:
    """
    Query for flow run alert policies.
    """
    return await models.flow_run_alert_policies.read_flow_run_alert_policies(
        session=session,
        offset=offset,
        limit=limit,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run_alert_policy(
    flow_run_alert_policy_id: UUID = Path(
        ..., description="The flow run alert policy id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a flow run alert policy by id.
    """
    result = await models.flow_run_alert_policies.delete_flow_run_alert_policy(
        session=session, flow_run_alert_policy_id=flow_run_alert_policy_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="flow run alert policy not found",
        )
