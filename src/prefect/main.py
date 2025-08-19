# Import user-facing API
from typing import Any
from prefect.states import State
from prefect.logging import get_run_logger
from prefect.flows import FlowDecorator, flow, Flow, serve, aserve
from prefect.transactions import Transaction
from prefect.tasks import task, Task
from prefect.context import tags
from prefect.utilities.annotations import unmapped, allow_failure
from prefect._result_records import ResultRecordMetadata
from prefect.flow_runs import pause_flow_run, resume_flow_run, suspend_flow_run
from prefect.client.orchestration import get_client
from prefect.client.cloud import get_cloud_client
import prefect.variables  # pyright: ignore[reportUnusedImport] # TODO: Does this need to be imported here?
import prefect.runtime  # pyright: ignore[reportUnusedImport] # TODO: Does this need to be imported here?

# Import modules that register types
import prefect.serializers  # pyright: ignore[reportUnusedImport]
import prefect.blocks.notifications  # pyright: ignore[reportUnusedImport]
import prefect.blocks.system  # pyright: ignore[reportUnusedImport]

# Initialize the process-wide profile and registry at import time
import prefect.context

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

_types: dict[str, Any] = dict(
    Task=Task,
    Flow=Flow,
    ResultRecordMetadata=ResultRecordMetadata,
)
prefect.context.FlowRunContext.model_rebuild(_types_namespace=_types)
prefect.context.TaskRunContext.model_rebuild(_types_namespace=_types)
prefect.client.schemas.State.model_rebuild(_types_namespace=_types)
prefect.client.schemas.StateCreate.model_rebuild(_types_namespace=_types)
prefect.client.schemas.OrchestrationResult.model_rebuild(_types_namespace=_types)
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

flow: FlowDecorator


# Declare API for type-checkers
__all__ = [
    "allow_failure",
    "flow",
    "Flow",
    "get_client",
    "get_cloud_client",
    "get_run_logger",
    "State",
    "tags",
    "task",
    "Task",
    "Transaction",
    "unmapped",
    "serve",
    "aserve",
    "pause_flow_run",
    "resume_flow_run",
    "suspend_flow_run",
]
