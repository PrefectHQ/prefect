import warnings

from prefect_gcp.bundles.execute import execute_bundle_from_gcs, main

warnings.warn(
    "`prefect_gcp.experimental.bundles.execute` has moved to "
    "`prefect_gcp.bundles.execute`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["execute_bundle_from_gcs", "main"]


if __name__ == "__main__":
    main()
