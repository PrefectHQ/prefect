from warnings import warn

from prefect._internal.compatibility.deprecated import generate_deprecation_message

warn(
    generate_deprecation_message(
        name="prefect_dbt.cli",
        start_date="Feb 2025",
        end_date="Jul 2025",
        help="Please use the PrefectDbtRunner class in prefect_dbt.core instead.",
    ),
    DeprecationWarning,
    stacklevel=2,
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
