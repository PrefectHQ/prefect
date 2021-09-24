import prefect

from prefect.utilities.logging import get_logger
from prefect.orion.utilities.server import OrionRouter

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
