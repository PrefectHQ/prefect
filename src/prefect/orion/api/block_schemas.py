"""
Routes for interacting with block schema objects.
"""
from typing import List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from fastapi import (
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    responses,
    status,
)

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_schemas", tags=["Block schemas"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block_schema(
    block_schema: schemas.actions.BlockSchemaCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.BlockSchema:
    try:
        model = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=block_schema,
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f'Block schema "{block_schema.name}/{block_schema.version}" already exists.',
        )

    return model


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_schema(
    block_schema_id: UUID = Path(..., description="The block schema id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a block schema by id.
    """
    result = await models.block_schemas.delete_block_schema(
        session=session, block_schema_id=block_schema_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block schema not found"
        )


@router.post("/filter")
async def read_block_schemas(
    block_schema_type: str = Body(
        None, description="The block schema type", alias="type"
    ),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockSchema]:
    """
    Read all block schemas, optionally filtered by type
    """
    result = await models.block_schemas.read_block_schemas(
        session=session,
        block_schema_type=block_schema_type,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/{name}/versions")
async def read_block_schemas_by_name(
    name: str = Path(..., description="The block schema name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockSchema]:
    """
    Read all block schema versions by name
    """
    result = await models.block_schemas.read_block_schemas(session=session, name=name)
    return result


@router.get("/{name}/versions/{version}")
async def read_block_schema_by_name_and_version(
    name: str = Path(..., description="The block schema name"),
    version: str = Path(..., description="The block schema version"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockSchema:
    """
    Read a block schema by name and version
    """
    result = await models.block_schemas.read_block_schema_by_name_and_version(
        session=session, name=name, version=version
    )

    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block schema not found")

    return result


@router.get("/{name}/block/{block_document_name}")
async def read_latest_block_document_by_name(
    block_schema_name: str = Path(
        ..., description="The block schema name", alias="name"
    ),
    block_document_name: str = Path(..., description="The block document name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockDocument:
    """
    Read the latest block document version that matches the provided block document name and name
    """
    model = await models.block_documents.read_block_document_by_name(
        session=session,
        name=block_document_name,
        block_schema_name=block_schema_name,
        version=None,
    )

    if not model:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Block document not found"
        )

    return await schemas.core.BlockDocument.from_orm_model(model)


@router.get("/{name}/versions/{version}/block/{block_document_name}")
async def read_block_by_name(
    block_schema_name: str = Path(
        ..., description="The block schema name", alias="name"
    ),
    block_schema_version: str = Path(
        ..., description="The block schema version", alias="version"
    ),
    block_document_name: str = Path(..., description="The block document name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockDocument:
    """
    Reads a block document corresponding to a specific block schema and version
    """
    model = await models.block_documents.read_block_document_by_name(
        session=session,
        name=block_document_name,
        block_schema_name=block_schema_name,
        version=block_schema_version,
    )

    if not model:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Block document not found"
        )

    return await schemas.core.BlockDocument.from_orm_model(model)
