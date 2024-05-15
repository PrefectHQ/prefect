# isort: skip_file

# Setup version and path constants

import sys
from typing import TYPE_CHECKING
from . import _version
import importlib
import pathlib

__version_info__ = _version.get_versions()
__version__ = __version_info__["version"]

# The absolute path to this module
__module_path__ = pathlib.Path(__file__).parent
# The absolute path to the root of the repository, only valid for use during development
__development_base_path__ = __module_path__.parents[1]

# The absolute path to the built UI within the Python module, used by
# `prefect server start` to serve a dynamic build of the UI
__ui_static_subpath__ = __module_path__ / "server" / "ui_build"

# The absolute path to the built UI within the Python module
__ui_static_path__ = __module_path__ / "server" / "ui"

del _version, pathlib

if TYPE_CHECKING:
    from prefect.client.orchestration import get_client, PrefectClient
    from prefect.context import tags
    from prefect.manifests import Manifest
    from prefect.client.cloud import get_cloud_client, CloudClient
    import prefect.variables
    import prefect.runtime
    from prefect.logging import get_run_logger
    from prefect.engine import pause_flow_run, resume_flow_run, suspend_flow_run
    from prefect.states import State
    from prefect.utilities.annotations import unmapped, allow_failure
    from prefect.flows import flow, serve
    from prefect.tasks import task

    # Import modules that register types
    import prefect.serializers
    import prefect.deprecated.data_documents
    import prefect.deprecated.packaging
    import prefect.blocks.kubernetes
    import prefect.blocks.notifications
    import prefect.blocks.system
    import prefect.infrastructure.process
    import prefect.infrastructure.kubernetes
    import prefect.infrastructure.container


_lazy_imports = {
    "get_client": "prefect.client.orchestration",
    "PrefectClient": "prefect.client.orchestration",
    "tags": "prefect.context",
    "Manifest": "prefect.manifests",
    "get_cloud_client": "prefect.client.cloud",
    "CloudClient": "prefect.client.cloud",
    "variables": "prefect.variables",
    "runtime": "prefect.runtime",
    "get_run_logger": "prefect.logging",
    "pause_flow_run": "prefect.engine",
    "resume_flow_run": "prefect.engine",
    "suspend_flow_run": "prefect.engine",
    "State": "prefect.states",
    "unmapped": "prefect.utilities.annotations",
    "allow_failure": "prefect.utilities.annotations",
    "flow": "prefect.flows",
    "serve": "prefect.flows",
    "task": "prefect.tasks",
    "prefect.serializers": "prefect.serializers",
    "prefect.deprecated.data_documents": "prefect.deprecated.data_documents",
    "prefect.deprecated.packaging": "prefect.deprecated.packaging",
    "prefect.blocks.kubernetes": "prefect.blocks.kubernetes",
    "prefect.blocks.notifications": "prefect.blocks.notifications",
    "prefect.blocks.system": "prefect.blocks.system",
    "prefect.infrastructure.process": "prefect.infrastructure.process",
    "prefect.infrastructure.kubernetes": "prefect.infrastructure.kubernetes",
    "prefect.infrastructure.container": "prefect.infrastructure.container",
}


def __getattr__(attr_name: str) -> object:
    if attr_name in _lazy_imports:
        module = importlib.import_module(_lazy_imports[attr_name])
        value = getattr(module, attr_name)
        setattr(sys.modules[__name__], attr_name, value)
        return value
    raise AttributeError(f"module {__name__} has no attribute {attr_name}")


# Import user-facing API
from prefect.deployments import deploy
from prefect.results import BaseResult

from prefect.flows import Flow
from prefect.tasks import Task


# Initialize the process-wide profile and registry at import time
import prefect.context

prefect.context.initialize_object_registry()

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

prefect.context.FlowRunContext.update_forward_refs(Flow=Flow)
prefect.context.TaskRunContext.update_forward_refs(Task=Task)
prefect.client.schemas.State.update_forward_refs(BaseResult=BaseResult)
prefect.client.schemas.StateCreate.update_forward_refs(BaseResult=BaseResult)


prefect.plugins.load_extra_entrypoints()

# Configure logging
import prefect.logging.configuration

prefect.logging.configuration.setup_logging()
prefect.logging.get_logger("profiles").debug(
    f"Using profile {prefect.context.get_settings_context().profile.name!r}"
)

# Ensure moved names are accessible at old locations
prefect.client.get_client = get_client
prefect.client.PrefectClient = PrefectClient


from prefect._internal.compatibility.deprecated import (
    inject_renamed_module_alias_finder,
)

inject_renamed_module_alias_finder()


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
    "serve",
    "deploy",
    "pause_flow_run",
    "resume_flow_run",
    "suspend_flow_run",
]
