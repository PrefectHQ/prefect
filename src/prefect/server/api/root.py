"""
Contains the `hello` route for testing and healthcheck purposes.
"""
from prefect._vendor.fastapi import Depends, status
from prefect._vendor.fastapi.responses import JSONResponse

from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="", tags=["Root"])


@router.get("/hello")
async def hello():
    """Say hello!"""
    return "👋"


@router.get("/ready")
async def perform_readiness_check(
    db: PrefectDBInterface = Depends(provide_database_interface),
):
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
