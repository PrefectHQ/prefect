"""
This module contains a collection of tasks for interacting with SQL Server databases via
the pyodbc library.
"""

try:
    from prefect.tasks.sql_server.sql_server import (
        SqlServerExecute,
        SqlServerExecuteMany,
        SqlServerFetch,
    )
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.sql_server` requires Prefect to be installed with the "sql_server" extra.'
    ) from err
