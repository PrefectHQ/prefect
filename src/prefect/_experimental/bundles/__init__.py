"""
Compatibility shim for the legacy `prefect._experimental.bundles` path.

The bundle implementation graduated to GA at `prefect.bundles` when the
infrastructure decorators feature became stable. This package keeps the
old import path importable (and `python -m`-runnable for the legacy
`...bundles.execute` entrypoint), but emits a `DeprecationWarning` so
consumers know to migrate to `prefect.bundles`.
"""

import warnings
from typing import Any

from prefect.bundles import (
    BundleCreationResult,
    BundleLauncher,
    BundleLauncherOverride,
    BundleLauncherSide,
    SerializedBundle,
    aupload_bundle_to_storage,
    convert_step_to_command,
    create_bundle_for_flow_run,
    execute_bundle_in_subprocess,
    extract_flow_from_bundle,
    upload_bundle_to_storage,
)
from prefect.bundles import _pin_prefect_in_bundle_step_requires  # noqa: F401

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


def __getattr__(name: str) -> Any:
    """Lazy-load `execute_bundle_from_file` from the `.execute` submodule
    so importing this package does not pre-populate
    `sys.modules["prefect._experimental.bundles.execute"]`. That would
    make `python -m prefect._experimental.bundles.execute` emit a
    `runpy` `RuntimeWarning` and hard-fail under
    `PYTHONWARNINGS=error`. Accessing the legacy `.execute` submodule
    by attribute (rather than importing it eagerly) still works because
    Python binds it on the package after a separate `from . import
    execute` (the legacy execute shim is reachable via plain
    `import prefect._experimental.bundles.execute`).
    """
    if name == "execute_bundle_from_file":
        from prefect.bundles.execute import execute_bundle_from_file

        return execute_bundle_from_file
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
