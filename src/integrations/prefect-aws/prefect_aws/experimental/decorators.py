import warnings

from prefect_aws.decorators import ecs

warnings.warn(
    "`prefect_aws.experimental.decorators` has moved to "
    "`prefect_aws.decorators`. The old import path will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ecs"]
