"""
Contains the `hello` route for testing and healthcheck purposes.
"""
from fastapi import Depends, Response, status
from prefect.server.utilities.server import PrefectRouter
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface

router = PrefectRouter(prefix="", tags=["Root"])


@router.get("/hello")
async def hello():
    """Say hello!"""
    return "👋"


@router.get("/ready")
async def peform_readiness_check(
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
):
    is_db_connectable = await db.is_db_connectable()

    if is_db_connectable:
        response.status_code = status.HTTP_200_OK
        return is_db_connectable

    response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return is_db_connectable
