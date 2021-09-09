from typing import List
from uuid import UUID

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
    nested = await session.begin_nested()
    try:
        result = await models.deployments.create_deployment(
            session=session, deployment=deployment
        )
        response.status_code = status.HTTP_201_CREATED
    except sa.exc.IntegrityError as exc:
        await nested.rollback()
        affected_rows = await models.deployments.update_deployment(
            session=session, deployment=deployment
        )
        stmt = await session.execute(
            sa.select(models.orm.Deployment).filter_by(
                flow_id=deployment.flow_id, name=deployment.name
            )
        )
        result = stmt.scalar()
    return result


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
