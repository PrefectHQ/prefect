"""
Routes for admin-level interactions with the Prefect REST API.
"""

import prefect
import prefect.settings
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(prefix="/admin", tags=["Admin"])


@router.get("/settings")
async def read_settings() -> prefect.settings.Settings:
    """
    Get the current Prefect REST API settings.

    Secret setting values will be obfuscated.
    """
    return prefect.settings.get_current_settings()


@router.get("/version")
async def read_version() -> str:
    """Returns the Prefect version number"""
    return prefect.__version__
