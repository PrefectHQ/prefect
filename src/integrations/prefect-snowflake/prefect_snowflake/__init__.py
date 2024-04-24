from . import _version
from prefect_snowflake.credentials import SnowflakeCredentials  # noqa
from prefect_snowflake.database import SnowflakeConnector  # noqa

__version__ = _version.__version__
