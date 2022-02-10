"""
This module contains a collection of tasks for interacting with Databricks resources.
"""

try:
    from prefect.tasks.databricks.databricks_submitjob import (
        DatabricksSubmitRun,
        DatabricksRunNow,
        DatabricksSubmitMultitaskRun,
    )
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.databricks` requires Prefect to be installed with the "databricks" extra.'
    ) from err

__all__ = ["DatabricksRunNow", "DatabricksSubmitRun", "DatabricksSubmitMultitaskRun"]
