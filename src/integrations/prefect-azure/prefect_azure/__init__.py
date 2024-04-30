from .credentials import (  # noqa
    AzureBlobStorageCredentials,
    AzureCosmosDbCredentials,
    AzureMlCredentials,
    AzureContainerInstanceCredentials,
)
from .workers.container_instance import AzureContainerWorker  # noqa
from .container_instance import AzureContainerInstanceJob  # noqa
from .blob_storage import AzureBlobStorageContainer  # noqa

__all__ = [
    "AzureBlobStorageCredentials",
    "AzureCosmosDbCredentials",
    "AzureMlCredentials",
    "AzureContainerInstanceCredentials",
    "AzureContainerInstanceJob",
    "AzureContainerWorker",
    "AzureBlobStorageContainer",
]

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
