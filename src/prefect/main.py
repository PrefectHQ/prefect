# Import user-facing API
from prefect.deployments import deploy
from prefect.states import State
from prefect.logging import get_run_logger
from prefect.flows import flow, Flow, serve
from prefect.transactions import Transaction
from prefect.tasks import task, Task
from prefect.context import tags
from prefect.utilities.annotations import unmapped, allow_failure
from prefect.results import BaseResult, ResultRecordMetadata
from prefect.flow_runs import pause_flow_run, resume_flow_run, suspend_flow_run
from prefect.client.orchestration import get_client, PrefectClient
from prefect.client.cloud import get_cloud_client, CloudClient
import prefect.variables
import prefect.runtime

# Import modules that register types
import prefect.serializers
import prefect.blocks.notifications
import prefect.blocks.system

# Initialize the process-wide profile and registry at import time
import prefect.context

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

prefect.context.FlowRunContext.model_rebuild(
    _types_namespace={
        "Flow": Flow,
        "BaseResult": BaseResult,
        "ResultRecordMetadata": ResultRecordMetadata,
    }
)
prefect.context.TaskRunContext.model_rebuild(
    _types_namespace={"Task": Task, "BaseResult": BaseResult}
)
prefect.client.schemas.State.model_rebuild(
    _types_namespace={
        "BaseResult": BaseResult,
        "ResultRecordMetadata": ResultRecordMetadata,
    }
)
prefect.client.schemas.StateCreate.model_rebuild(
    _types_namespace={
        "BaseResult": BaseResult,
        "ResultRecordMetadata": ResultRecordMetadata,
    }
)
Transaction.model_rebuild()

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
