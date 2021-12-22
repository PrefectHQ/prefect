"""
This module contains a collection of tasks to interact with Mixpanel APIs
"""

try:
    from prefect.tasks.mixpanel.mixpanel_tasks import MixpanelExportTask
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.mixpanel` requires Prefect to be installed with the "mixpanel" extra.'
    ) from err
