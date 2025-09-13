"""
Contains the `hello` route for testing and healthcheck purposes.
"""

import os

from fastapi import Depends, status
from fastapi.responses import JSONResponse

from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.server import PrefectRouter
from prefect.settings.context import get_current_settings

router: PrefectRouter = PrefectRouter(prefix="", tags=["Root"])


@router.get("/hello")
async def hello() -> str:
    """Say hello!"""
    return "👋"


@router.get("/ready")
async def perform_readiness_check(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> JSONResponse:
    is_db_connectable = await db.is_db_connectable()

    if is_db_connectable:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "OK"},
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"message": "Database is not available"},
    )


if get_current_settings().testing.test_mode:

    @router.get("/pid")
    async def pid() -> JSONResponse:
        """
        Returns the process ID of the current process.

        Used for testing multi-worker server.
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK, content={"pid": os.getpid()}
        )
