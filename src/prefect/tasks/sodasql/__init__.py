"""
This module contains a collection of tasks to run Data Quality tests using soda-sql library
"""
from warnings import warn

warn(
    f"soda-sql has been deprecated. We cannot guarantee that the SodaSparkScan "
    "task will continue to function properly.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from prefect.tasks.sodasql.sodasql_tasks import SodaSQLScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.sodasql` requires Prefect to be installed with the "sodasql" extra.'
    ) from err

__all__ = ["SodaSQLScan"]
