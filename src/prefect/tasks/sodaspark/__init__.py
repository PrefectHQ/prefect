"""
This module contains a collection of tasks to run Data Quality tests using soda-spark library
"""

try:
    from prefect.tasks.sodaspark.sodaspark_tasks import SodaSparkScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.sodaspark` requires Prefect to be installed with the "sodaspark" extra.'
    ) from err

__all__ = ["SodaSparkScan"]
