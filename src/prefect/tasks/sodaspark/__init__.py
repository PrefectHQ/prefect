"""
This module contains a collection of tasks to run Data Quality tests using soda-spark library
"""
from warnings import warn

warn(
    f"soda-spark has been deprecated. We cannot guarantee that the SodaSparkScan "
    "task will continue to function properly.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from prefect.tasks.sodaspark.sodaspark_tasks import SodaSparkScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.sodaspark` requires Prefect to be installed with the "sodaspark" extra.'
    ) from err

__all__ = ["SodaSparkScan"]
