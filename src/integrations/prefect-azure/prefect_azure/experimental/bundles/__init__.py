import warnings

from prefect_azure.bundles.execute import execute_bundle_from_azure_blob_storage
from prefect_azure.bundles.upload import upload_bundle_to_azure_blob_storage

warnings.warn(
    "`prefect_azure.experimental.bundles` has moved to "
    "`prefect_azure.bundles`. The old import path will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "upload_bundle_to_azure_blob_storage",
    "execute_bundle_from_azure_blob_storage",
]
