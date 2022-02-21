"""
Routes for interacting with block objects.
"""
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, responses, status

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/blocks", tags=["Blocks"])


@router.post("/")
async def create_block(
    block: schemas.actions.BlockCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Block:

    # hydrate the input model into a full model
    block_data_model = schemas.core.Block(**block.dict())

    try:
        model = await models.blocks.create_block(
            session=session, block=block_data_model
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Block already exists",
        )

    if model.created >= pendulum.now():
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id}")
async def read_block(
    block_id: UUID = Path(..., description="The block id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):

    block = await models.blocks.read_block_by_id(session=session, block_id=block_id)

    if not block:
        return responses.JSONResponse(
            status_code=404, content={"message": "Block not found"}
        )

    return block


@router.get("/name/{name}")
async def read_block_by_name(
    name: str = Path(..., description="The block name", alias="name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):

    block = await models.blocks.read_block_by_name(session=session, name=name)

    if not block:
        return responses.JSONResponse(
            status_code=404, content={"message": "Block not found"}
        )

    return block


@router.delete("/name/{name}")
async def delete_block_by_name(
    name: str = Path(..., description="The block name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.blocks.delete_block_by_name(session=session, name=name)
    if not result:
        return responses.JSONResponse(
            status_code=404, content={"message": "Block not found"}
        )


@router.patch("/name/{name}")
async def update_block_data(
    name: str,
    block: schemas.actions.BlockUpdate,
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.blocks.update_block(
        session=session,
        name=name,
        block=block,
    )

    if not result:
        return responses.JSONResponse(
            status_code=404, content={"message": "Block not found"}
        )
