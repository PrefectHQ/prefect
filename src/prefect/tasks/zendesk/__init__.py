"""
This module contains a collection of tasks to export data from Zendesk
"""

try:
    from prefect.tasks.zendesk.zendesk_tasks import *
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.zendesk` requires Prefect to be installed with the "zendesk" extra.'
    ) from err
