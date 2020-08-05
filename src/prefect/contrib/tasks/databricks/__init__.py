"""
A collection of tasks for interacting with Databricks.
"""
try:
    from prefect.contrib.tasks.databricks.databricks import (
        DatabricksRunSubmit,
        DATABRICKS_API_VERSION,
    )
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.databricks` requires Prefect to be installed with the "databricks" extra.'
    )
