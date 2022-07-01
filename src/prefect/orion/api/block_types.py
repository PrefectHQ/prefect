from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Query, status

import prefect
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_types", tags=["Block types"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block_type(
    block_type: schemas.actions.BlockTypeCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockType:
    """
    Create a new block type
    """
    # API-created blocks cannot start with the word "Prefect"
    # as it is reserved for system use
    if block_type.name.lower().startswith("prefect"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Block type names beginning with 'Prefect' are reserved.",
        )
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
    block_types: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schemas: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockType]:
    """
    Gets all block types. Optionally limit return with limit and offset.
    """
    return await models.block_types.read_block_types(
        session=session,
        limit=limit,
        offset=offset,
        block_type_filter=block_types,
        block_schema_filter=block_schemas,
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
    db_block_type = await models.block_types.read_block_type(
        session=session, block_type_id=block_type_id
    )
    if db_block_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")
    elif db_block_type.is_protected:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="protected block types cannot be updated.",
        )
    await models.block_types.update_block_type(
        session=session, block_type=block_type, block_type_id=block_type_id
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_type(
    block_type_id: UUID = Path(..., description="The block type ID", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    db_block_type = await models.block_types.read_block_type(
        session=session, block_type_id=block_type_id
    )
    if db_block_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block type not found"
        )
    elif db_block_type.is_protected:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="protected block types cannot be deleted.",
        )
    await models.block_types.delete_block_type(
        session=session, block_type_id=block_type_id
    )


@router.get("/name/{name}/block_documents", tags=router.tags + ["Block documents"])
async def read_block_documents_for_block_type(
    session: sa.orm.Session = Depends(dependencies.get_session),
    block_type_name: str = Path(..., description="The block type name", alias="name"),
    include_secrets: bool = Query(
        False, description="Whether to include sensitive values in the block document."
    ),
) -> List[schemas.core.BlockDocument]:
    block_type = await models.block_types.read_block_type_by_name(
        session=session, block_type_name=block_type_name
    )
    if not block_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block type not found")
    return await models.block_documents.read_block_documents(
        session=session,
        block_document_filter=schemas.filters.BlockDocumentFilter(
            block_type_id=dict(any_=[block_type.id])
        ),
        include_secrets=include_secrets,
    )


@router.get(
    "/name/{block_type_name}/block_documents/name/{block_document_name}",
    tags=router.tags + ["Block documents"],
)
async def read_block_document_by_name_for_block_type(
    session: sa.orm.Session = Depends(dependencies.get_session),
    block_type_name: str = Path(
        ...,
        description="The block type name",
    ),
    block_document_name: str = Path(..., description="The block type name"),
    include_secrets: bool = Query(
        False, description="Whether to include sensitive values in the block document."
    ),
) -> schemas.core.BlockDocument:
    block_document = await models.block_documents.read_block_document_by_name(
        session=session,
        block_type_name=block_type_name,
        name=block_document_name,
        include_secrets=include_secrets,
    )
    if not block_document:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Block document not found"
        )
    return block_document


@router.post("/install_system_block_types")
async def install_system_block_types(
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """Install block types that the system expects to be present"""
    for block in [
        prefect.blocks.system.JSON,
        prefect.blocks.system.String,
        prefect.blocks.system.DateTime,
        prefect.blocks.system.EnvironmentVariable,
    ]:
        block_type = block._to_block_type()
        block_type.is_protected = True

        block_type = await models.block_types.create_block_type(
            session=session, block_type=block_type, override=True
        )
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=block._to_block_schema(block_type_id=block_type.id),
            override=True,
        )
