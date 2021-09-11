from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

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
    deployment = await models.deployments.create_deployment(
        session=session, deployment=deployment
    )

    if deployment.created >= now:
        response.status_code = status.HTTP_201_CREATED
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


@router.get("/")
async def read_deployments(
    pagination: schemas.pagination.Pagination = Body(schemas.pagination.Pagination()),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Deployment]:
    """
    Query for deployments
    """
    return await models.deployments.read_deployments(
        session=session, offset=pagination.offset, limit=pagination.limit
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
    return result


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
