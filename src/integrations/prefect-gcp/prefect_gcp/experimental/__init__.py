import warnings

from prefect_gcp.decorators import cloud_run, vertex_ai

warnings.warn(
    "`prefect_gcp.experimental` has moved to `prefect_gcp.decorators`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["cloud_run", "vertex_ai"]
