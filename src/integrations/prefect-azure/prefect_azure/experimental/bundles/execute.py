import warnings

from prefect_azure.bundles.execute import (
    execute_bundle_from_azure_blob_storage,
    main,
)

warnings.warn(
    "`prefect_azure.experimental.bundles.execute` has moved to "
    "`prefect_azure.bundles.execute`. Reconfigure your work pool storage to "
    "use the new path; the old path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["execute_bundle_from_azure_blob_storage", "main"]


if __name__ == "__main__":
    main()
