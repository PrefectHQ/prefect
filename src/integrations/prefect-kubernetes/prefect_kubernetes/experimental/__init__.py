import warnings

from prefect_kubernetes.decorators import kubernetes

warnings.warn(
    "`prefect_kubernetes.experimental` has moved to "
    "`prefect_kubernetes.decorators`. The old import path will be removed "
    "in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["kubernetes"]
