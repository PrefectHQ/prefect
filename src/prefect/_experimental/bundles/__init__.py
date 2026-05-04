"""
Compatibility shim for the legacy `prefect._experimental.bundles` path.

The bundle implementation graduated to GA at `prefect.bundles` when the
infrastructure decorators feature became stable. This package keeps the
old import path importable (and `python -m`-runnable for the legacy
`...bundles.execute` entrypoint), but emits a `DeprecationWarning` so
consumers know to migrate to `prefect.bundles`.
"""

import warnings

from prefect.bundles import (
    BundleCreationResult,
    BundleLauncher,
    BundleLauncherOverride,
    BundleLauncherSide,
    SerializedBundle,
    aupload_bundle_to_storage,
    convert_step_to_command,
    create_bundle_for_flow_run,
    execute_bundle_from_file,
    execute_bundle_in_subprocess,
    extract_flow_from_bundle,
    upload_bundle_to_storage,
)
from prefect.bundles import _pin_prefect_in_bundle_step_requires  # noqa: F401

# Eagerly import the local `execute` submodule (a thin shim) so that
# `prefect._experimental.bundles.execute` is bound as a package attribute
# during import — preserving the legacy submodule-attribute access
# pattern after a plain `import prefect._experimental.bundles`.
from . import execute  # noqa: F401

warnings.warn(
    "`prefect._experimental.bundles` has moved to `prefect.bundles`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BundleCreationResult",
    "BundleLauncher",
    "BundleLauncherOverride",
    "BundleLauncherSide",
    "SerializedBundle",
    "aupload_bundle_to_storage",
    "convert_step_to_command",
    "create_bundle_for_flow_run",
    "execute_bundle_from_file",
    "execute_bundle_in_subprocess",
    "extract_flow_from_bundle",
    "upload_bundle_to_storage",
]
