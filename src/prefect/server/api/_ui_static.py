"""Private helpers for UI static-file management during server startup."""

from __future__ import annotations

import errno
import logging
import pathlib
import shutil
from dataclasses import dataclass
from typing import Literal

UIVersion = Literal["v1", "v2"]


@dataclass(frozen=True)
class UIBundle:
    version: UIVersion
    source_static_path: str
    static_dir: str
    base_url: str
    cache_key: str


def log_ui_static_copy_error(
    bundle: UIBundle,
    exc: OSError,
    logger: logging.Logger,
) -> None:
    """Log an actionable error when copying a UI bundle's static files fails."""
    if exc.errno == errno.ENOSPC:
        try:
            disk_path = pathlib.Path(bundle.static_dir)
            while not disk_path.exists():
                disk_path = disk_path.parent
            usage = shutil.disk_usage(disk_path)
            available_mb = usage.free / (1024 * 1024)
        except OSError:
            available_mb = None
        try:
            required_bytes = sum(
                f.stat().st_size
                for f in pathlib.Path(bundle.source_static_path).rglob("*")
                if f.is_file()
            )
            required_mb = required_bytes / (1024 * 1024)
        except OSError:
            required_mb = None

        space_detail = ""
        if required_mb is not None and available_mb is not None:
            space_detail = (
                f" Required: {required_mb:.1f} MB, available: {available_mb:.1f} MB."
            )
        elif available_mb is not None:
            space_detail = f" Available disk space: {available_mb:.1f} MB."

        logger.error(
            "Not enough disk space to unpack %s UI static"
            " files at %s.%s To resolve this, increase the"
            " size of the volume mounted at that path or set"
            " PREFECT_UI_STATIC_DIRECTORY to a location with"
            " sufficient space.",
            bundle.version.upper(),
            bundle.static_dir,
            space_detail,
        )
    elif isinstance(exc, PermissionError):
        logger.error(
            "Failed to create %s UI static directory at %s:"
            " %s. That UI will not be available. To resolve"
            " this, set PREFECT_UI_STATIC_DIRECTORY to a"
            " writable directory.",
            bundle.version.upper(),
            bundle.static_dir,
            exc,
        )
    else:
        logger.error(
            "Failed to create %s UI static directory at %s:"
            " %s. That UI will not be available.",
            bundle.version.upper(),
            bundle.static_dir,
            exc,
        )
