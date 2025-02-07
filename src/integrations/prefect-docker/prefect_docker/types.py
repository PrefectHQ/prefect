import re
from typing import Annotated

from pydantic import AfterValidator


def assert_volume_str(volume: str) -> str:
    """
    Validate a Docker volume string and raise `ValueError` if invalid.
    """
    if not isinstance(volume, str):  # type: ignore[reportUnnecessaryIsInstance]
        raise ValueError("Invalid volume specification: must be a string")
    vol = volume.strip()
    if not vol:
        raise ValueError("Invalid volume specification: cannot be empty")
    pattern = re.compile(
        r"^(?:"
        r"(?P<container_only>/[^:]+)"  # anonymous volume: container path only
        r"|"
        r"(?P<host>(?:[A-Za-z]:\\|\\\\|/)?[^:]+):"
        r"(?P<container_path>(/)?[^:]+)"
        r"(?::(?P<options>.+))?"
        r")$"
    )
    match = pattern.match(vol)
    if not match:
        raise ValueError(f"Invalid volume specification: {volume}")
    # Anonymous volume: just a container path (must start with '/')
    if match.group("container_only"):
        return vol
    host_part = match.group("host")
    container_path = match.group("container_path")
    options = match.group("options")
    # Determine if host is a bind mount (absolute host path) or a named volume.
    is_unix_host = host_part.startswith("/")
    is_windows_drive = re.match(r"^[A-Za-z]:\\", host_part) is not None
    is_unc = host_part.startswith("\\\\")
    if is_unix_host or is_windows_drive or is_unc:
        # For bind mounts, container path must be absolute.
        if not container_path.startswith("/"):
            raise ValueError("For bind mounts, container path must be absolute")
    else:
        # For named volumes, host must not contain path separators.
        if "/" in host_part or "\\" in host_part:
            raise ValueError(f"Invalid volume name: {host_part}")
    if options is not None:
        if options not in ("ro", "rw"):
            raise ValueError(
                f"Invalid volume option: {options!r}. Must be 'ro' or 'rw'"
            )
    return vol


VolumeStr = Annotated[str, AfterValidator(assert_volume_str)]
