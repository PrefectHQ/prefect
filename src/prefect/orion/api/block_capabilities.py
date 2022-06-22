"""
Routes for interacting with block capabilities.
"""
from typing import List

import sqlalchemy as sa
from fastapi import Depends

from prefect.orion import models
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/block_capabilities", tags=["Block capabilities"])


@router.get("/")
async def read_available_block_capabilities(
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[str]:
    return await models.block_schemas.read_available_block_capabilities(session=session)
