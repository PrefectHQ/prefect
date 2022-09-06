"""
Routes for admin-level interactions with the Orion API.
"""

from fastapi import Body, Depends, Response, status

import prefect
import prefect.settings
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/admin", tags=["Admin"])


@router.get("/settings")
async def read_settings() -> prefect.settings.Settings:
    """Get the current Orion settings"""
    return prefect.settings.get_current_settings()


@router.get("/version")
async def read_version() -> str:
    """Returns the Prefect version number"""
    return prefect.__version__


@router.post("/database/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_database(
    db: OrionDBInterface = Depends(provide_database_interface),
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
    async with db.session_context(begin_transaction=True) as session:
        for table in reversed(db.Base.metadata.sorted_tables):
            await session.execute(table.delete())


@router.post("/database/drop", status_code=status.HTTP_204_NO_CONTENT)
async def drop_database(
    db: OrionDBInterface = Depends(provide_database_interface),
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

    await db.drop_db()


@router.post("/database/create", status_code=status.HTTP_204_NO_CONTENT)
async def create_database(
    db: OrionDBInterface = Depends(provide_database_interface),
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

    await db.create_db()
