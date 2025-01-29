"""
Utilities for working with file systems
"""

import os
import pathlib
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Any, AnyStr, Optional, Union, cast

# fsspec has no stubs, see https://github.com/fsspec/filesystem_spec/issues/625
import fsspec  # type: ignore
import pathspec
from fsspec.core import OpenFile  # type: ignore
from fsspec.implementations.local import LocalFileSystem  # type: ignore

import prefect


def create_default_ignore_file(path: str) -> bool:
    """
    Creates default ignore file in the provided path if one does not already exist; returns boolean specifying
    whether a file was created.
    """
    _path = pathlib.Path(path)
    ignore_file = _path / ".prefectignore"
    if ignore_file.exists():
        return False
    default_file = pathlib.Path(prefect.__module_path__) / ".prefectignore"
    with ignore_file.open(mode="w") as f:
        f.write(default_file.read_text())
    return True


def filter_files(
    root: str = ".",
    ignore_patterns: Optional[Iterable[AnyStr]] = None,
    include_dirs: bool = True,
) -> set[str]:
    """
    This function accepts a root directory path and a list of file patterns to ignore, and returns
    a list of files that excludes those that should be ignored.

    The specification matches that of [.gitignore files](https://git-scm.com/docs/gitignore).
    """
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns or [])
    ignored_files = {p.path for p in spec.match_tree_entries(root)}
    if include_dirs:
        all_files = {p.path for p in pathspec.util.iter_tree_entries(root)}
    else:
        all_files = set(pathspec.util.iter_tree_files(root))
    included_files = all_files - ignored_files
    return included_files


chdir_lock: threading.Lock = threading.Lock()


def _normalize_path(path: Union[str, Path]) -> str:
    """
    Normalize a path, handling UNC paths on Windows specially.
    """
    path = Path(path)

    # Handle UNC paths on Windows differently
    if os.name == "nt" and str(path).startswith("\\\\"):
        # For UNC paths, use absolute() instead of resolve()
        # to avoid the Windows path resolution issues
        return str(path.absolute())
    else:
        try:
            # For non-UNC paths, try resolve() first
            return str(path.resolve())
        except OSError:
            # Fallback to absolute() if resolve() fails
            return str(path.absolute())


@contextmanager
def tmpchdir(path: str):
    """
    Change current-working directories for the duration of the context,
    with special handling for UNC paths on Windows.
    """
    path = _normalize_path(path)

    if os.path.isfile(path) or (not os.path.exists(path) and not path.endswith("/")):
        path = os.path.dirname(path)

    owd = os.getcwd()

    with chdir_lock:
        try:
            # On Windows with UNC paths, we need to handle the directory change carefully
            if os.name == "nt" and path.startswith("\\\\"):
                # Use os.path.abspath to handle UNC paths
                os.chdir(os.path.abspath(path))
            else:
                os.chdir(path)
            yield path
        finally:
            os.chdir(owd)


def filename(path: str) -> str:
    """Extract the file name from a path with remote file system support"""
    try:
        of: OpenFile = cast(OpenFile, fsspec.open(path))  # type: ignore  # no typing stubs available
        sep = cast(str, of.fs.sep)  # type: ignore  # no typing stubs available
    except (ImportError, AttributeError):
        sep = "\\" if "\\" in path else "/"
    return path.split(sep)[-1]


def is_local_path(path: Union[str, pathlib.Path, Any]) -> bool:
    """Check if the given path points to a local or remote file system"""
    if isinstance(path, str):
        try:
            of = cast(OpenFile, fsspec.open(path))  # type: ignore  # no typing stubs available
        except ImportError:
            # The path is a remote file system that uses a lib that is not installed
            return False
    elif isinstance(path, pathlib.Path):
        return True
    else:
        of = path

    return isinstance(of.fs, LocalFileSystem)


def to_display_path(
    path: Union[pathlib.Path, str],
    relative_to: Optional[Union[pathlib.Path, str]] = None,
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


def relative_path_to_current_platform(path_str: str) -> Path:
    """
    Converts a relative path generated on any platform to a relative path for the
    current platform.
    """

    return Path(PureWindowsPath(path_str).as_posix())


def get_open_file_limit() -> int:
    """Get the maximum number of open files allowed for the current process"""

    try:
        if os.name == "nt":
            import ctypes

            return ctypes.cdll.ucrtbase._getmaxstdio()
        else:
            import resource

            soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
            return soft_limit
    except Exception:
        # Catch all exceptions, as ctypes can raise several errors
        # depending on what went wrong. Return a safe default if we
        # can't get the limit from the OS.
        return 200
