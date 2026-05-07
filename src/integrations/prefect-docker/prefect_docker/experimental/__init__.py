import warnings

from prefect_docker.decorators import docker

warnings.warn(
    "`prefect_docker.experimental` has moved to `prefect_docker.decorators`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["docker"]
