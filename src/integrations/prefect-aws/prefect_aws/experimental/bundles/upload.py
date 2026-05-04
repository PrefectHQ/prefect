import warnings

from prefect_aws.bundles.upload import (
    UploadResult,
    main,
    upload_bundle_to_s3,
)

warnings.warn(
    "`prefect_aws.experimental.bundles.upload` has moved to "
    "`prefect_aws.bundles.upload`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["UploadResult", "main", "upload_bundle_to_s3"]


if __name__ == "__main__":
    main()
