import warnings

from prefect_azure.bundles.upload import (
    UploadBundleToAzureBlobStorageOutput,
    main,
    upload_bundle_to_azure_blob_storage,
)

warnings.warn(
    "`prefect_azure.experimental.bundles.upload` has moved to "
    "`prefect_azure.bundles.upload`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "UploadBundleToAzureBlobStorageOutput",
    "main",
    "upload_bundle_to_azure_blob_storage",
]


if __name__ == "__main__":
    main()
