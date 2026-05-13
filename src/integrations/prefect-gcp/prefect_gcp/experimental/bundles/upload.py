import warnings

from prefect_gcp.bundles.upload import (
    UploadBundleToGcsOutput,
    main,
    upload_bundle_to_gcs,
)

warnings.warn(
    "`prefect_gcp.experimental.bundles.upload` has moved to "
    "`prefect_gcp.bundles.upload`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["UploadBundleToGcsOutput", "main", "upload_bundle_to_gcs"]


if __name__ == "__main__":
    main()
