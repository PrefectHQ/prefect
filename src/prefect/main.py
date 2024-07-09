# Import user-facing API
from prefect.states import State
from prefect.flows import flow, Flow, serve
from prefect.transactions import Transaction
from prefect.tasks import task, Task
from prefect.context import tags
from prefect.results import BaseResult

# Initialize the process-wide profile and registry at import time
import prefect.context

# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

prefect.context.FlowRunContext.model_rebuild()
prefect.context.TaskRunContext.model_rebuild()
prefect.client.schemas.State.model_rebuild()
prefect.client.schemas.StateCreate.model_rebuild()
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
    "flow",
    "Flow",
    "State",
    "tags",
    "task",
    "Task",
    "Transaction",
    "serve",
]
