"""
This module contains a collection of tasks for interacting with snowflake databases via
the snowflake-connector-python library.
"""

try:
    from prefect.tasks.snowflake.snowflake import SnowflakeQuery
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.snowflake` requires Prefect to be installed with the "snowflake" extra.'
    ) from err
