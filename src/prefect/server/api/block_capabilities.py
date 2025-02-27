"""
Routes for interacting with block capabilities.
"""

from typing import List

from fastapi import Depends

from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(
    prefix="/block_capabilities", tags=["Block capabilities"]
)


@router.get("/")
async def read_available_block_capabilities(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[str]:
    """
    Get available block capabilities.

    For more information, see https://docs.prefect.io/v3/develop/blocks.
    """
    async with db.session_context() as session:
        return await models.block_schemas.read_available_block_capabilities(
            session=session
        )
