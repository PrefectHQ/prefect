"""
This module contains a collection of tasks for interacting with Toloka API.

All Toloka related tasks can be authenticated using the `TOLOKA_TOKEN` Prefect Secret that should contain Toloka API OAuth token. See [Third Party Authentication](../../../orchestration/recipes/third_party_auth.html) for more information.
"""
try:
    from .helpers import *
    from .operations import *
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.tasks` requires Prefect to be installed with the "toloka" extra.'
    ) from err
