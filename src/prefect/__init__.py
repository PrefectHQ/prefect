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

# Import user-facing API
from prefect.orion.schemas.states import State
from prefect.logging import get_run_logger
from prefect.flows import flow, Flow
from prefect.tasks import task, Task
from prefect.context import tags
from prefect.client import get_client
from prefect.deployments import Deployment

# Import modules that register types
import prefect.serializers
import prefect.packaging
import prefect.blocks.kubernetes
import prefect.blocks.notifications
import prefect.blocks.storage
import prefect.blocks.system

# Initialize the process-wide profile and registry at import time
import prefect.context

prefect.context.enter_root_settings_context()
prefect.context.initialize_object_registry()

# The context needs updated references for flows and tasks
prefect.context.FlowRunContext.update_forward_refs(Flow=Flow)
prefect.context.TaskRunContext.update_forward_refs(Task=Task)

# Ensure collections are imported and have the opportunity to register types
import prefect.plugins

prefect.plugins.load_prefect_collections()

# Declare API
__all__ = [
    "Deployment",
    "flow",
    "Flow",
    "get_client",
    "get_run_logger",
    "State",
    "tags",
    "task",
    "Task",
]
