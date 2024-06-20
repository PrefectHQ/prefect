# Import user-facing API
import prefect.blocks.notifications
import prefect.blocks.system

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

# Initialize the process-wide profile and registry at import time
import prefect.context
import prefect.runtime

# Import modules that register types
import prefect.serializers
import prefect.variables
from prefect.client.orchestration import get_client
from prefect.context import tags
from prefect.deployments import deploy
from prefect.flow_runs import pause_flow_run, resume_flow_run, suspend_flow_run
from prefect.flows import Flow, flow, serve
from prefect.logging import get_run_logger
from prefect.manifests import Manifest
from prefect.states import State
from prefect.tasks import Task, task
from prefect.transactions import Transaction
from prefect.utilities.annotations import allow_failure, unmapped

prefect.context.FlowRunContext.model_rebuild()
prefect.context.TaskRunContext.model_rebuild()
prefect.client.schemas.State.model_rebuild()
prefect.client.schemas.StateCreate.model_rebuild()
Transaction.model_rebuild()


prefect.plugins.load_extra_entrypoints()

# Configure logging
import prefect.logging.configuration

prefect.logging.configuration.setup_logging()
prefect.logging.get_logger("profiles").debug(
    f"Using profile {prefect.context.get_settings_context().profile.name!r}"
)

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
    "Transaction",
    "unmapped",
    "serve",
    "deploy",
    "pause_flow_run",
    "resume_flow_run",
    "suspend_flow_run",
]
