import warnings

# Import from the legacy submodules (which themselves shim to
# `prefect_azure.bundles.*`) so that
# `prefect_azure.experimental.bundles.upload` and `.execute` are bound
# as package attributes during import — preserving the legacy
# submodule-attribute access pattern.
from .execute import execute_bundle_from_azure_blob_storage
from .upload import upload_bundle_to_azure_blob_storage

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
