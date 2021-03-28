"""
This module contains a collection of tasks for interacting with snowflake databases via
the snowflake-connector-python library.
"""

try:
    from prefect.tasks.soda.soda import SodaSQLScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.soda.soda` requires Prefect to be installed with the "sodasql" extra.'
    ) from err
