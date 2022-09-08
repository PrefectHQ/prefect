"""
Routes for interacting with block capabilities.
"""
from typing import List

from fastapi import Depends

from prefect.orion import models
from prefect.orion.database.dependencies import (
    OrionDBInterface,
    provide_database_interface,
)
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_capabilities", tags=["Block capabilities"])


@router.get("/")
async def read_available_block_capabilities(
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[str]:
    async with db.session_context() as session:
        return await models.block_schemas.read_available_block_capabilities(
            session=session
        )
