"""
This module contains a collection of tasks for interacting with Dremio Query Engine via
the pyarrow library.
"""
try:
    from prefect.tasks.dremio.dremio import DremioFetch
except ImportError as import_error:
    raise ImportError(
        'Using `prefect.tasks.dremio` requires Prefect to be installed with the "dremio" extra.'
    ) from import_error
