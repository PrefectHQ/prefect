"""
This module contains a collection of tasks for interacting with Azure resources.
"""

try:
    from prefect.tasks.azure.blobstorage import BlobStorageDownload, BlobStorageUpload
    from prefect.tasks.azure.cosmosdb import (
        CosmosDBCreateItem,
        CosmosDBReadItems,
        CosmosDBQueryItems,
    )
    from prefect.tasks.azure.datafactory import (
        DatafactoryCreate,
        PipelineCreate,
        PipelineRun,
    )
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.azure` requires Prefect to be installed with the "azure" extra.'
    ) from err

__all__ = [
    "BlobStorageDownload",
    "BlobStorageUpload",
    "CosmosDBCreateItem",
    "CosmosDBQueryItems",
    "CosmosDBReadItems",
    "DatafactoryCreate",
    "PipelineCreate",
    "PipelineRun",
]
