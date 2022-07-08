"""
Routes for interacting with block schema objects.
"""
from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, Response, status

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models.block_schemas import MissingBlockTypeException
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_schemas", tags=["Block schemas"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block_schema(
    block_schema: schemas.actions.BlockSchemaCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.BlockSchema:

    # check if the requested block type is protected
    block_type = await models.block_types.read_block_type(
        session=session, block_type_id=block_schema.block_type_id
    )
    if block_type is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Block type {block_schema.block_type_id} not found.",
        )
    elif block_type.is_protected:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Block schemas for protected block types cannot be created.",
        )

    try:
        model = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=block_schema,
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Identical block schema already exists.",
        )
    except MissingBlockTypeException as ex:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(ex))

    return model


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_schema(
    block_schema_id: UUID = Path(..., description="The block schema id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a block schema by id.
    """
    block_schema = await models.block_schemas.read_block_schema(
        session=session, block_schema_id=block_schema_id
    )
    if not block_schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block schema not found"
        )

    if block_schema.block_type.is_protected:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Block schemas for protected block types cannot be deleted.",
        )

    await models.block_schemas.delete_block_schema(
        session=session, block_schema_id=block_schema_id
    )


@router.post("/filter")
async def read_block_schemas(
    block_schemas: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockSchema]:
    """
    Read all block schemas, optionally filtered by type
    """
    result = await models.block_schemas.read_block_schemas(
        session=session,
        block_schema_filter=block_schemas,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/{id}")
async def read_block_schema_by_id(
    block_schema_id: UUID = Path(..., description="The block schema id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockSchema:
    """
    Get a block schema by id.
    """
    block_schema = await models.block_schemas.read_block_schema(
        session=session, block_schema_id=block_schema_id
    )
    if not block_schema:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block schema not found")
    return block_schema


@router.get("/checksum/{checksum}")
async def read_block_schema_by_checksum(
    block_schema_checksum: str = Path(
        ..., description="The block schema checksum", alias="checksum"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockSchema:
    block_schema = await models.block_schemas.read_block_schema_by_checksum(
        session=session, checksum=block_schema_checksum
    )
    if not block_schema:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block schema not found")
    return block_schema
