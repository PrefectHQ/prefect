"""
Routes for interacting with block objects.
"""
from typing import List, Optional
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


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block(
    block: schemas.actions.BlockCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.Block:
    try:
        model = await models.blocks.create_block(session=session, block=block)
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Block already exists",
        )

    return await schemas.core.Block.from_orm_model(session=session, orm_block=model)


@router.post("/filter")
async def read_blocks(
    limit: int = dependencies.LimitBody(),
    block_spec_type: str = Body(None, description="The block spec type"),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Block]:
    """
    Query for blocks.
    """
    result = await models.blocks.read_blocks(
        session=session,
        block_spec_type=block_spec_type,
        offset=offset,
        limit=limit,
    )

    return [await schemas.core.Block.from_orm_model(session, b) for b in result]


@router.get("/{id}")
async def read_block_by_id(
    block_id: UUID = Path(..., description="The block id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Block:
    model = await models.blocks.read_block_by_id(session=session, block_id=block_id)
    if not model:
        return responses.JSONResponse(
            status_code=404, content={"message": "Block not found"}
        )
    return await schemas.core.Block.from_orm_model(session=session, orm_block=model)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    block_id: str = Path(..., description="The block id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.blocks.delete_block(session=session, block_id=block_id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_block_data(
    block: schemas.actions.BlockUpdate,
    block_id: str = Path(..., description="The block id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.blocks.update_block(
        session=session,
        block_id=id,
        block=block,
    )

    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")


@router.post("/{id}/set_default_storage_block", status_code=status.HTTP_204_NO_CONTENT)
async def set_default_storage_block(
    block_id: str = Path(..., description="The block id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    try:
        await models.blocks.set_default_storage_block(
            session=session, block_id=block_id
        )
    except ValueError as exc:
        if "Block not found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
            )
        elif "Block spec type must be STORAGE" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Specified block is not a storage block",
            )
        else:
            raise


@router.post("/get_default_storage_block")
async def get_default_storage_block(
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> Optional[schemas.core.Block]:
    model = await models.blocks.get_default_storage_block(session=session)
    if model:
        return await schemas.core.Block.from_orm_model(session=session, orm_block=model)
    else:
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/clear_default_storage_block", status_code=status.HTTP_204_NO_CONTENT)
async def clear_default_storage_block(
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    await models.blocks.clear_default_storage_block(session=session)
