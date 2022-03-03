"""
This module contains a collection of tasks to interact with Trasform metrics layer.
"""

try:
    from prefect.tasks.sodasql.sodasql_tasks import SodaSQLScan
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.sodasql` requires Prefect to be installed with the "sodasql" extra.'
    ) from err

__all__ = ["SodaSQLScan"]
