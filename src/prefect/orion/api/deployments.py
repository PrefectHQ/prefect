import datetime
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/")
async def create_deployment(
    deployment: schemas.actions.DeploymentCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Deployment:
    """Gracefully creates a new deployment from the provided schema. If a deployment with the
    same name and flow_id already exists, the deployment is updated."""
    now = pendulum.now()
    model = await models.deployments.create_deployment(
        session=session, deployment=deployment
    )

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED

    # this deployment might have already scheduled runs (if it's being upserted)
    # so we delete them all here; if the upserted deployment has an active schedule
    # then its runs will be rescheduled.
    delete_query = sa.delete(models.orm.FlowRun).where(
        models.orm.FlowRun.deployment_id == model.id,
        models.orm.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
        models.orm.FlowRun.auto_scheduled.is_(True),
    )
    await session.execute(delete_query)

    # proactively schedule the deployment
    if deployment.schedule and deployment.is_schedule_active:
        await models.deployments.schedule_runs(
            session=session,
            deployment_id=model.id,
        )

    return model


@router.get("/name/{flow_name}/{deployment_name}")
async def read_deployment_by_name(
    flow_name: str = Path(..., description="The name of the flow"),
    deployment_name: str = Path(..., description="The name of the deployment"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Deployment:
    """
    Get a deployment using the name of the flow and the deployment
    """
    deployment = await models.deployments.read_deployment_by_name(
        session=session, name=deployment_name, flow_name=flow_name
    )
    if not deployment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return deployment


@router.get("/{id}")
async def read_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Deployment:
    """
    Get a deployment by id
    """
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    return deployment


@router.post("/filter")
async def read_deployments(
    limit: int = Body(
        settings.orion.api.default_limit, ge=0, le=settings.orion.api.default_limit
    ),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Deployment]:
    """
    Query for deployments
    """
    return await models.deployments.read_deployments(
        session=session, offset=offset, limit=limit
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a deployment by id
    """
    result = await models.deployments.delete_deployment(
        session=session, deployment_id=deployment_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )


@router.post("/{id}/schedule")
async def schedule_deployment(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    start_time: datetime.datetime = Body(
        None, description="The earliest date to schedule"
    ),
    end_time: datetime.datetime = Body(None, description="The latest date to schedule"),
    max_runs: int = Body(None, description="The maximum number of runs to schedule"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> None:
    """
    Schedule runs for a deployment. For backfills, provide start/end times in the past.
    """
    await models.deployments.schedule_runs(
        session=session,
        deployment_id=deployment_id,
        start_time=start_time,
        end_time=end_time,
        max_runs=max_runs,
    )


@router.post("/{id}/set_schedule_active")
async def set_schedule_active(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> None:
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    deployment.is_schedule_active = True
    await session.flush()

    # proactively schedule the deployment
    if deployment.schedule:
        await models.deployments.schedule_runs(
            session=session,
            deployment_id=deployment_id,
        )


@router.post("/{id}/set_schedule_inactive")
async def set_schedule_inactive(
    deployment_id: UUID = Path(..., description="The deployment id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> None:
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )
    deployment.is_schedule_active = False
    await session.flush()

    # delete any future scheduled runs that were auto-scheduled
    delete_query = sa.delete(models.orm.FlowRun).where(
        models.orm.FlowRun.deployment_id == deployment_id,
        models.orm.FlowRun.state_type == schemas.states.StateType.SCHEDULED.value,
        models.orm.FlowRun.auto_scheduled.is_(True),
    )
    await session.execute(delete_query)
