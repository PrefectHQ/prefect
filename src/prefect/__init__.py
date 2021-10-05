# Internal constants
from . import _version
import pathlib as _pathlib

__version__ = _version.get_versions()["version"]
__root_path__ = _pathlib.Path(__file__).parents[2]
__ui_static_path__ = __root_path__ / "orion" / "ui"

del _version
del _pathlib

# Prepare settings and logging first
from prefect.utilities.settings import settings
from prefect.utilities.logging import setup_logging

setup_logging(settings)

# Import the serializers so they are registered
import prefect.serializers

# User-facing API
from prefect.orion.schemas.states import State
from prefect.flows import flow
from prefect.tasks import task
from prefect.engine import tags
