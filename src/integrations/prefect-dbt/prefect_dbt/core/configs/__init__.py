from .base import TargetConfigs, GlobalConfigs, MissingExtrasRequireError  # noqa

try:
    from .snowflake import SnowflakeTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .bigquery import BigQueryTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass

try:
    from .postgres import PostgresTargetConfigs  # noqa
except MissingExtrasRequireError:
    pass
