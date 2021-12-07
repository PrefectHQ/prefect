"""
This module contains a collection of tasks for interacting with firebolt databases via
the firebolt-sdk library.
"""

try:
    from prefect.tasks.firebolt.firebolt import FireboltQuery, FireboltQueryGetData
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.firebolt` requires Prefect to be installed with the "firebolt" extra.'
    ) from err
