import sqlalchemy as sa
from fastapi import Depends, status, Response, Body

import prefect
from prefect.utilities.logging import get_logger
from prefect.orion.utilities.server import OrionRouter
from prefect.orion.api import dependencies
from prefect.orion.utilities.database import Base

router = OrionRouter(prefix="/admin", tags=["Admin"])


@router.get("/hello")
def hello():
    return "👋"


@router.get("/settings")
def read_settings() -> prefect.utilities.settings.Settings:
    return prefect.settings


@router.get("/version")
def read_version() -> str:
    """Returns the Prefect version number"""
    return prefect.__version__


@router.post("/database/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_database(
    session: sa.orm.Session = Depends(dependencies.get_session),
    confirm: bool = Body(
        False,
        embed=True,
        description="Pass confirm=True to confirm you want to modify the database.",
    ),
    response: Response = None,
):
    """Clear all database tables without dropping them."""
    if not confirm:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return

    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(table.delete())


@router.post("/database/drop", status_code=status.HTTP_204_NO_CONTENT)
async def drop_database(
    session: sa.orm.Session = Depends(dependencies.get_session),
    confirm: bool = Body(
        False,
        embed=True,
        description="Pass confirm=True to confirm you want to modify the database.",
    ),
    response: Response = None,
):
    """Drop all database objects."""
    if not confirm:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return
    await prefect.orion.utilities.database.drop_db(session.bind)


@router.post("/database/create", status_code=status.HTTP_204_NO_CONTENT)
async def create_database(
    session: sa.orm.Session = Depends(dependencies.get_session),
    confirm: bool = Body(
        False,
        embed=True,
        description="Pass confirm=True to confirm you want to modify the database.",
    ),
    response: Response = None,
):
    """Create all database objects."""
    if not confirm:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return
    await prefect.orion.utilities.database.create_db(session.bind)
