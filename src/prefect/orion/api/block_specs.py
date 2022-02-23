"""
Routes for interacting with block objects.
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

router = OrionRouter(prefix="/block_specs", tags=["Block Specs"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_block_spec(
    block_spec: schemas.actions.BlockSpecCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.BlockSpec:
    try:
        model = await models.block_specs.create_block_spec(
            session=session,
            block_spec=block_spec,
        )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f'Block spec "{block_spec.name}/{block_spec.version}" already exists.',
        )

    return model


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_spec(
    block_spec_id: UUID = Path(..., description="The block spec id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """
    Delete a block spec by id.
    """
    result = await models.block_specs.delete_block_spec(
        session=session, block_spec_id=block_spec_id
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block spec not found"
        )


@router.post("/filter")
async def read_block_specs(
    block_spec_type: str = Body(None, description="The block spec type", alias="type"),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockSpec]:
    """
    Read all block specs, optionally filtered by type
    """
    result = await models.block_specs.read_block_specs(
        session=session,
        block_spec_type=block_spec_type,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/{name}/versions")
async def read_block_specs_by_name(
    name: str = Path(..., description="The block spec name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.BlockSpec]:
    """
    Read all block spec versions by name
    """
    result = await models.block_specs.read_block_specs(session=session, name=name)
    return result


@router.get("/{name}/versions/{version}")
async def read_block_spec_by_name_and_version(
    name: str = Path(..., description="The block spec name"),
    version: str = Path(..., description="The block spec version"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.BlockSpec:
    """
    Read a block spec by name and version
    """
    result = await models.block_specs.read_block_spec_by_name_and_version(
        session=session, name=name, version=version
    )

    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block spec not found")

    return result


@router.get("/{name}/block/{block_name}")
async def read_latest_block_by_name(
    block_spec_name: str = Path(..., description="The block spec name", alias="name"),
    block_name: str = Path(..., description="The block name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Block:
    """
    Read the latest block version that matches the provided block name and name
    """
    model = await models.blocks.read_block_by_name(
        session=session,
        name=block_name,
        block_spec_name=block_spec_name,
        version=None,
    )

    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")

    return await schemas.core.Block.from_orm_model(model)


@router.get("/{name}/versions/{version}/block/{block_name}")
async def read_block_by_name(
    block_spec_name: str = Path(..., description="The block spec name", alias="name"),
    block_spec_version: str = Path(
        ..., description="The block spec version", alias="version"
    ),
    block_name: str = Path(..., description="The block name"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Block:
    """
    Reads a block corresponding to a specific block spec and version
    """
    model = await models.blocks.read_block_by_name(
        session=session,
        name=block_name,
        block_spec_name=block_spec_name,
        version=block_spec_version,
    )

    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")

    return await schemas.core.Block.from_orm_model(model)
