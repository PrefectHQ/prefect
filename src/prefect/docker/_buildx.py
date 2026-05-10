"""
Compatibility shim for the legacy `prefect.docker._buildx` path.

The buildx utilities moved to `prefect._internal.buildx` as part of the
internal module consolidation. This module re-exports the public symbols
from the new location so that separately-released integration packages
(e.g. `prefect-docker`) that pin older Prefect versions continue to work.
"""

from prefect._internal.buildx import (
    buildx_build_image,
    buildx_push_image,
)

__all__ = [
    "buildx_build_image",
    "buildx_push_image",
]
