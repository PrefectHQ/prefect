# isort: skip_file

# Setup version and path constants

from . import _version
import importlib
import pathlib
import warnings
import sys

__version_info__ = _version.get_versions()
__version__ = __version_info__["version"]

# The absolute path to this module
__module_path__ = pathlib.Path(__file__).parent
# The absolute path to the root of the repository, only valid for use during development.
__root_path__ = __module_path__.parents[1]
# The absolute path to the built UI within the Python module
__ui_static_path__ = __module_path__ / "orion" / "ui"

del _version, pathlib


# Import user-facing API
from prefect.states import State
from prefect.logging import get_run_logger
from prefect.flows import flow, Flow
from prefect.tasks import task, Task
from prefect.context import tags
from prefect.manifests import Manifest
from prefect.utilities.annotations import unmapped, allow_failure
from prefect.results import BaseResult
from prefect.engine import pause_flow_run, resume_flow_run
from prefect.client.orion import get_client, OrionClient
from prefect.client.cloud import get_cloud_client, CloudClient

# Import modules that register types
import prefect.serializers
import prefect.deprecated.data_documents
import prefect.packaging
import prefect.blocks.kubernetes
import prefect.blocks.notifications
import prefect.blocks.system
import prefect.infrastructure.process
import prefect.infrastructure.kubernetes
import prefect.infrastructure.docker

# Initialize the process-wide profile and registry at import time
import prefect.context

prefect.context.initialize_object_registry()

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

prefect.context.FlowRunContext.update_forward_refs(Flow=Flow)
prefect.context.TaskRunContext.update_forward_refs(Task=Task)
prefect.client.schemas.State.update_forward_refs(
    BaseResult=BaseResult, DataDocument=prefect.deprecated.data_documents.DataDocument
)

# Ensure collections are imported and have the opportunity to register types
import prefect.plugins

prefect.plugins.load_prefect_collections()


# Configure logging
import prefect.logging.configuration

prefect.logging.configuration.setup_logging()


# Ensure moved names are accessible at old locations
import prefect.client

prefect.client.get_client = get_client
prefect.client.OrionClient = OrionClient

# Attempt to warn users who are importing Prefect 1.x attributes that they may
# have accidentally installed Prefect 2.x

PREFECT_1_ATTRIBUTES = [
    "prefect.Client",
    "prefect.Parameter",
    "prefect.api",
    "prefect.apply_map",
    "prefect.case",
    "prefect.config",
    "prefect.context",
    "prefect.flatten",
    "prefect.mapped",
    "prefect.models",
    "prefect.resource_manager",
]


class Prefect1ImportInterceptor(importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname in PREFECT_1_ATTRIBUTES:
            warnings.warn(
                f"Attempted import of {fullname!r}, which is part of Prefect 1.x, "
                f"while Prefect {__version__} is installed. If you're "
                "upgrading you'll need to update your code, see the Prefect "
                "2.x migration guide: `https://orion-docs.prefect.io/migration_guide/`. "
                "Otherwise ensure that your code is pinned to the expected version."
            )


if not hasattr(sys, "frozen"):
    sys.meta_path = [Prefect1ImportInterceptor()] + sys.meta_path


# Declare API for type-checkers
__all__ = [
    "allow_failure",
    "flow",
    "Flow",
    "get_client",
    "get_run_logger",
    "Manifest",
    "State",
    "tags",
    "task",
    "Task",
    "unmapped",
]
