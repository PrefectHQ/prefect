"""
This module contains a task for interacting with dbt via the shell.
"""

try:
    from prefect.tasks.dbt.dbt import DbtShellTask
except ImportError:
    raise ImportError("Using `prefect.tasks.dbt` requires dbt to be installed.")
