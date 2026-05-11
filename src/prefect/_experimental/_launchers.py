"""
Compatibility shim for the legacy `prefect._experimental._launchers` path.

The launcher utilities graduated to GA at `prefect._internal.launchers` when the
infrastructure decorators feature became stable. This module re-exports
the public symbols from the new location and emits a
`DeprecationWarning` so consumers know to migrate.
"""

import warnings

from prefect._internal.launchers import (
    get_launcher_for_side,
    normalize_launcher,
    resolve_bundle_step_with_launcher,
    validate_bundle_step_launcher,
)

warnings.warn(
    "`prefect._experimental._launchers` has moved to `prefect._internal.launchers`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "get_launcher_for_side",
    "normalize_launcher",
    "resolve_bundle_step_with_launcher",
    "validate_bundle_step_launcher",
]
