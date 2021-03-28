"""
This module contains a collection of tasks to run Data Quality tests using soda-sql library
"""

try:
    from prefect.tasks.soda.soda import SodaSQLScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.soda.soda` requires Prefect to be installed with the "sodasql" extra.'
    ) from err
