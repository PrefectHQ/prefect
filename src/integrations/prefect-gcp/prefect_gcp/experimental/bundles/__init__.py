import warnings

# Import from the legacy submodules (which themselves shim to
# `prefect_gcp.bundles.*`) so that `prefect_gcp.experimental.bundles.upload`
# and `.execute` are bound as package attributes during import —
# preserving the legacy submodule-attribute access pattern.
from .execute import execute_bundle_from_gcs
from .upload import upload_bundle_to_gcs

warnings.warn(
    "`prefect_gcp.experimental.bundles` has moved to `prefect_gcp.bundles`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["upload_bundle_to_gcs", "execute_bundle_from_gcs"]
