# Internal constants
from . import _version
import pathlib as _pathlib
import os as _os

__version__ = _version.get_versions()["version"]
# The absolute path to this module
__module_path__ = _pathlib.Path(__file__).parent
# The absolute path to the root of the repository
__root_path__ = __module_path__.parents[1]
# The absolute path to the built UI within the Python module
__ui_static_path__ = __module_path__ / "orion" / "ui"

del _version
del _pathlib

# Prepare settings and logging first
from prefect.utilities.settings import settings
from prefect.utilities.logging import setup_logging

if not _os.path.exists(settings.home):
    _os.makedirs(settings.home, exist_ok=True)

setup_logging(settings)

# Import the serializers so they are registered
import prefect.serializers

# User-facing API
from prefect.orion.schemas.states import State
from prefect.flows import flow
from prefect.tasks import task
from prefect.engine import tags
