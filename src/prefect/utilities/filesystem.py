"""
Utilities for working with file systems
"""
import os
import pathlib
from contextlib import contextmanager
from typing import Union

import fsspec
from fsspec.core import OpenFile
from fsspec.implementations.local import LocalFileSystem


@contextmanager
def tmpchdir(path: str):
    """
    Change current-working directories for the duration of the context
    """
    path = os.path.abspath(path)
    if os.path.isfile(path) or (not os.path.exists(path) and not path.endswith("/")):
        path = os.path.dirname(path)

    owd = os.getcwd()

    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(owd)


def filename(path: str) -> str:
    """Extract the file name from a path with remote file system support"""
    try:
        of: OpenFile = fsspec.open(path)
        sep = of.fs.sep
    except (ImportError, AttributeError):
        sep = "\\" if "\\" in path else "/"
    return path.split(sep)[-1]


def is_local_path(path: Union[str, pathlib.Path, OpenFile]):
    """Check if the given path points to a local or remote file system"""
    if isinstance(path, str):
        try:
            of = fsspec.open(path)
        except ImportError:
            # The path is a remote file system that uses a lib that is not installed
            return False
    elif isinstance(path, pathlib.Path):
        return True
    elif isinstance(path, OpenFile):
        of = path
    else:
        raise TypeError(f"Invalid path of type {type(path).__name__!r}")

    return type(of.fs) == LocalFileSystem


def to_display_path(
    path: Union[pathlib.Path, str], relative_to: Union[pathlib.Path, str] = None
) -> str:
    """
    Convert a path to a displayable path. The absolute path or relative path to the
    current (or given) directory will be returned, whichever is shorter.
    """
    path, relative_to = (
        pathlib.Path(path).resolve(),
        pathlib.Path(relative_to or ".").resolve(),
    )
    relative_path = str(path.relative_to(relative_to))
    absolute_path = str(path)
    return relative_path if len(relative_path) < len(absolute_path) else absolute_path
