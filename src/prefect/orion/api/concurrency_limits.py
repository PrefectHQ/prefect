"""
Routes for interacting with concurrency limit objects.
"""
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/concurrency_limits", tags=["Concurrency Limits"])


@router.post("/")
async def create_concurrency_limit(
    concurrency_limit: schemas.actions.ConcurrencyLimitCreate,
    response: Response,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:

    # hydrate the input model into a full model
    concurrency_limit_model = schemas.core.ConcurrencyLimit(**concurrency_limit.dict())

    async with db.session_context(begin_transaction=True) as session:

        model = await models.concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=concurrency_limit_model
        )

    if model.created >= pendulum.now():
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id}")
async def read_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    """
    Get a concurrency limit by id.

    The `active slots` field contains a list of TaskRun IDs currently using a
    concurrency slot for the specified tag.
    """
    async with db.session_context() as session:
        model = await models.concurrency_limits.read_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
    return model


@router.get("/tag/{tag}")
async def read_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name", alias="tag"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    """
    Get a concurrency limit by tag.

    The `active slots` field contains a list of TaskRun IDs currently using a
    concurrency slot for the specified tag.
    """

    async with db.session_context() as session:
        model = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session=session, tag=tag
        )

    if not model:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
    return model


@router.post("/filter")
async def read_concurrency_limits(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.ConcurrencyLimit]:
    """
    Query for concurrency limits.

    For each concurrency limit the `active slots` field contains a list of TaskRun IDs
    currently using a concurrency slot for the specified tag.
    """
    async with db.session_context() as session:
        return await models.concurrency_limits.read_concurrency_limits(
            session=session,
            limit=limit,
            offset=offset,
        )


@router.delete("/{id}")
async def delete_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        result = await models.concurrency_limits.delete_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


@router.delete("/tag/{tag}")
async def delete_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        result = await models.concurrency_limits.delete_concurrency_limit_by_tag(
            session=session, tag=tag
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
