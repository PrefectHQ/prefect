from prefect._vendor.fastapi import Depends, Query

from prefect.logging import get_logger
from prefect.server import models, schemas
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

logger = get_logger("server.api")

router = PrefectRouter(prefix="/csrf-token")


@router.get("")
async def create_csrf_token(
    db: PrefectDBInterface = Depends(provide_database_interface),
    client: str = Query(..., description="The client to create a CSRF token for"),
) -> schemas.core.CsrfToken:
    """Create or update a CSRF token for a client"""
    async with db.session_context(begin_transaction=True) as session:
        return await models.csrf_token.create_or_update_csrf_token(
            session=session, client=client
        )
