# Setup version and path constants

from . import _version
import pathlib

__version_info__ = _version.get_versions()
__version__ = __version_info__["version"]

# The absolute path to this module
__module_path__ = pathlib.Path(__file__).parent
# The absolute path to the root of the repository
__root_path__ = __module_path__.parents[1]
# The absolute path to the built UI within the Python module
__ui_static_path__ = __module_path__ / "orion" / "ui"

del _version, pathlib

# User-facing API
# For details on the import syntax, see https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md#library-interface

from .orion.schemas.states import State
from .logging import get_run_logger
from .flows import flow
from .tasks import task
from .context import tags
from .client import get_client

# Import the serializers so they are registered
import prefect.serializers

# Initialize the process level profile at import time
import prefect.context

prefect.context.enter_global_profile()
