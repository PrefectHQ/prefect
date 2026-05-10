"""
Compatibility shim for the legacy `prefect.docker._buildx` path.

The buildx utilities moved to `prefect._internal.buildx` as part of the
internal module consolidation. This module re-exports the public symbols
from the new location so that separately-released integration packages
(e.g. `prefect-docker`) that pin older Prefect versions continue to work.
"""

import warnings

from prefect._internal.buildx import (
    buildx_build_image,
    buildx_push_image,
)

warnings.warn(
    "`prefect.docker._buildx` has moved to `prefect._internal.buildx`. "
    "The old import path will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "buildx_build_image",
    "buildx_push_image",
]
