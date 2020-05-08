"""
This module contains a tasks for interacting with dbt via the shell.
"""

try:
    from prefect.tasks.dbt.dbt import DbtShellTask
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.dbt` requires Prefect to be installed with the "dbt" extra.'
    )
