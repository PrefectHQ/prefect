"""
This module contains a task for starting and monitoring Fivetran connector sync jobs
"""
try:
    from prefect.tasks.fivetran.fivetran import FivetranSyncTask
except ImportError as import_error:
    raise ImportError(
        'Using `prefect.tasks.fivetran` requires Prefect to be installed with the "fivetran" extra.'
    ) from import_error
