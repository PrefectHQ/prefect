import warnings

from prefect_aws.bundles.execute import (
    DownloadResult,
    download_bundle_from_s3,
    execute_bundle_from_s3,
    main,
)

warnings.warn(
    "`prefect_aws.experimental.bundles.execute` has moved to "
    "`prefect_aws.bundles.execute`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DownloadResult",
    "download_bundle_from_s3",
    "execute_bundle_from_s3",
    "main",
]


if __name__ == "__main__":
    main()
