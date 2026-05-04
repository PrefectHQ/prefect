import warnings

from prefect_azure.decorators import azure_container_instance

warnings.warn(
    "`prefect_azure.experimental.decorators` has moved to "
    "`prefect_azure.decorators`. The old import path will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["azure_container_instance"]
