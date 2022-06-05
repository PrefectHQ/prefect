from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, status

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.models import block_documents
from prefect.orion.schemas.core import BlockDocument
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_types", tags=["Block documents"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block_type(
    block_type: schemas.actions.BlockTypeCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockType:
    """
    Create a new block type
    """
    try:
        created_block_type = await models.block_types.create_block_type(
            session, block_type=block_type
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f'Block type with name "{block_type.name}" already exists',
        )
    return created_block_type


@router.get("/{id}")
async def read_block_type_by_id(
    block_type_id: UUID = Path(..., description="The block type ID", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockType:
    """
    Get a block type by ID.
    """
    block_type = await models.block_types.read_block_type(
        session=session, block_type_id=block_type_id
    )
    if not block_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")
    return block_type


@router.get("/name/{name}")
async def read_block_type_by_name(
    block_type_name: str = Path(..., description="The block type name", alias="name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockType:
    """
    Get a block type by name.
    """
    block_type = await models.block_types.read_block_type_by_name(
        session=session, block_type_name=block_type_name
    )
    if not block_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")
    return block_type


@router.post("/filter")
async def read_block_types(
    session: sa.orm.Session = Depends(dependencies.get_session),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
) -> List[schemas.core.BlockType]:
    """
    Gets all block types. Optionally limit return with limit and offset.
    """
    return await models.block_types.read_block_types(
        session=session, limit=limit, offset=offset
    )


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_block_type(
    block_type: schemas.actions.BlockTypeUpdate,
    block_type_id: UUID = Path(..., description="The block type ID", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Update a block type.
    """
    result = await models.block_types.update_block_type(
        session=session, block_type=block_type, block_type_id=block_type_id
    )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_type(
    block_type_id: UUID = Path(..., description="The block type ID", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    result = await models.block_types.delete_block_type(
        session=session, block_type_id=block_type_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block type not found"
        )


@router.get("/name/{name}/block_documents", tags=["Block documents"])
async def read_block_documents_for_block_type(
    session: sa.orm.Session = Depends(dependencies.get_session),
    block_type_name: str = Path(..., description="The block type name", alias="name"),
) -> List[schemas.core.BlockDocument]:
    block_type = await models.block_types.read_block_type_by_name(
        session=session, block_type_name=block_type_name
    )
    if not block_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")
    return await models.block_documents.read_block_documents(
        session=session, block_type_id=block_type.id
    )


@router.get(
    "/name/{block_type_name}/block_documents/name/{block_document_name}",
    tags=["Block documents"],
)
async def read_block_document_by_name_for_block_type(
    session: sa.orm.Session = Depends(dependencies.get_session),
    block_type_name: str = Path(
        ...,
        description="The block type name",
    ),
    block_document_name: str = Path(..., description="The block type name"),
) -> schemas.core.BlockDocument:
    block_document = await models.block_documents.read_block_document_by_name(
        session=session, block_type_name=block_type_name, name=block_document_name
    )
    if not block_document:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Block document not found"
        )
    return block_document
