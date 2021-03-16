"""
This module contains a collection of tasks for interacting with Azure Machine Learning Service resources.
"""

try:
    from prefect.tasks.azureml.dataset import (
        DatasetCreateFromDelimitedFiles,
        DatasetCreateFromParquetFiles,
        DatasetCreateFromFiles,
    )

    from prefect.tasks.azureml.datastore import (
        DatastoreRegisterBlobContainer,
        DatastoreList,
        DatastoreGet,
        DatastoreUpload,
    )

except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.azureml` requires Prefect to be installed with the "azure" extra.'
    ) from err
