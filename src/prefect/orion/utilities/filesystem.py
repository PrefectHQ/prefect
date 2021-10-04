"""
Filesystem utilities.
"""

import fsspec

# Supported file system schemes
FILE_SYSTEM_SCHEMES = ("s3", "file")


def write_blob(blob: bytes, path: str) -> bool:
    """Write a blob to a file path."""
    with fsspec.open(path, mode="wb") as fp:
        fp.write(blob)
    return True


def read_blob(path: str) -> bytes:
    """Read a blob from a file path."""
    with fsspec.open(path, mode="rb") as fp:
        blob = fp.read()
    return blob
