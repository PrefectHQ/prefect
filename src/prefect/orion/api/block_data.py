"""
Routes for interacting with block data objects.
"""
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_data", tags=["Block data"])


@router.post("/")
async def create_block_data(
    block_data: schemas.actions.BlockDataCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.BlockData:

    # hydrate the input model into a full model
    block_data_model = schemas.core.BlockData(**block_data.dict())

    try:
        model = await models.block_data.create_block_data(
            session=session, block_data=block_data_model
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.status.HTTP_400_BAD_REQUEST,
            detail="Block data already exists",
        )

    if model.created >= pendulum.now():
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id}")
async def read_block_data(
    block_data_id: UUID = Path(..., description="The block data id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):

    block = await models.block_data.read_block_data(
        session=session, block_data_id=block_data_id
    )

    if not block:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block data not found")

    return block


@router.get("/name/{name}")
async def read_block_data_by_name(
    name: str = Path(..., description="The block name", alias="name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):

    block = await models.block_data.read_block_data_by_name(session=session, name=name)

    if not block:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block data not found")

    return block


@router.delete("/name/{name}")
async def delete_block_data_by_name(
    name: str = Path(..., description="The block name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.block_data.delete_block_data_by_name(
        session=session, name=name
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block data not found"
        )
