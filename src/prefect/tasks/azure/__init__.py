"""
This module contains a collection of tasks for interacting with Azure resources.

Note that all tasks require a Prefect Secret called `"AZ_CREDENTIALS"` that should be a JSON
document with two keys: `"ACCOUNT_NAME"` and `"ACCOUNT_KEY"`.
"""

try:
    from prefect.tasks.azure.blobstorage import BlobStorageDownload, BlobStorageUpload
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.azure` requires Prefect to be installed with the "azure" extra.'
    )
