"""
This module contains a collection of tasks for interacting with Postgres databases via
the psycopg2 library.
"""

try:
    from prefect.tasks.postgres.postgres import (
        PostgresExecute,
        PostgresExecuteMany,
        PostgresFetch,
    )
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.postgres` requires Prefect to be installed with the "postgres" extra.'
    ) from err

__all__ = ["PostgresExecute", "PostgresExecuteMany", "PostgresFetch"]
