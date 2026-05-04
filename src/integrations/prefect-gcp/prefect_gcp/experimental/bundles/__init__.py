import warnings

from prefect_gcp.bundles.execute import execute_bundle_from_gcs
from prefect_gcp.bundles.upload import upload_bundle_to_gcs

warnings.warn(
    "`prefect_gcp.experimental.bundles` has moved to `prefect_gcp.bundles`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["upload_bundle_to_gcs", "execute_bundle_from_gcs"]
