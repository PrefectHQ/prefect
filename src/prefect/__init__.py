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
import prefect.settings
from prefect.logging.configuration import setup_logging
from prefect.logging.loggers import get_run_logger

if not _os.path.exists(prefect.settings.from_env().home):
    _os.makedirs(prefect.settings.from_env().home, exist_ok=True)

setup_logging(prefect.settings.from_env())

# Import the serializers so they are registered
import prefect.serializers

# User-facing API
from prefect.orion.schemas.states import State
from prefect.flows import flow
from prefect.tasks import task
from prefect.context import tags
