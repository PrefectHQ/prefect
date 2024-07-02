# Import user-facing API

from prefect.states import State
from prefect.logging import get_run_logger
from prefect.transactions import Transaction
from prefect.context import tags
from prefect.manifests import Manifest
from prefect.utilities.annotations import unmapped, allow_failure
from prefect.results import BaseResult
from prefect.client.orchestration import get_client


# Perform any forward-ref updates needed for Pydantic models
import prefect.client.schemas

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
    "allow_failure",
    "get_client",
    "get_run_logger",
    "Manifest",
    "State",
    "tags",
    "Transaction",
    "unmapped",
]
