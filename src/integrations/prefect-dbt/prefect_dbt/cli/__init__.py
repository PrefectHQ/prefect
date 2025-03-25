import warnings

warnings.warn(
    "prefect_dbt.cli is deprecated and will be removed in a future release. "
    "Please use prefect_dbt.core instead.",
    UserWarning,
    stacklevel=1,
)

from .credentials import DbtCliProfile  # noqa
from .commands import DbtCoreOperation  # noqa

from .configs.base import (  # noqa
    TargetConfigs,
    GlobalConfigs,
    MissingExtrasRequireError,
)

try:
    from .configs.snowflake import SnowflakeTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .configs.bigquery import BigQueryTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .configs.postgres import PostgresTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

# Re-export all imports to maintain the public API
__all__ = [
    "DbtCliProfile",
    "DbtCoreOperation",
    "TargetConfigs",
    "GlobalConfigs",
    "MissingExtrasRequireError",
    "SnowflakeTargetConfigs",
    "BigQueryTargetConfigs",
    "PostgresTargetConfigs",
]
