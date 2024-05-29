# pyright: reportPrivateUsage=false
from . import _version

from .cloud import DbtCloudCredentials  # noqa
from .cli import (  # noqa
    DbtCliProfile,
    GlobalConfigs,
    MissingExtrasRequireError,
    TargetConfigs,
    DbtCoreOperation,
)

try:
    from .cli.configs.snowflake import SnowflakeTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .cli.configs.bigquery import BigQueryTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .cli.configs.postgres import PostgresTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

__all__ = [
    "DbtCloudCredentials",
    "DbtCliProfile",
    "GlobalConfigs",
    "MissingExtrasRequireError",
    "TargetConfigs",
    "DbtCoreOperation",
    "SnowflakeTargetConfigs",
    "BigQueryTargetConfigs",
    "PostgresTargetConfigs",
]

__version__ = getattr(_version, "__version__")
