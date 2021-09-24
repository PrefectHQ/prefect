import sqlalchemy as sa
from fastapi import Depends, status

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


@router.delete(
    "/universe", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False
)
async def clear_database(
    session: sa.orm.Session = Depends(dependencies.get_session),
):
    """Clears all database tables"""
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(table.delete())
