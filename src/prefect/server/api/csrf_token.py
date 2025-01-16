from typing import TYPE_CHECKING

from fastapi import Depends, Query, status
from starlette.exceptions import HTTPException

from prefect.logging import get_logger
from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import PREFECT_SERVER_CSRF_PROTECTION_ENABLED

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("server.api")

router: PrefectRouter = PrefectRouter(prefix="/csrf-token")


@router.get("")
async def create_csrf_token(
    db: PrefectDBInterface = Depends(provide_database_interface),
    client: str = Query(..., description="The client to create a CSRF token for"),
) -> schemas.core.CsrfToken:
    """Create or update a CSRF token for a client"""
    if PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value() is False:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSRF protection is disabled.",
        )

    async with db.session_context(begin_transaction=True) as session:
        token = await models.csrf_token.create_or_update_csrf_token(
            session=session, client=client
        )
        await models.csrf_token.delete_expired_tokens(session=session)

    return token
