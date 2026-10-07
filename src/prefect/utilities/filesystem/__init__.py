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


def _walk_tree(
    root: str,
    spec: pathspec.GitIgnoreSpec,
    include_dirs: bool,
    follow_links: Optional[bool] = None,
) -> tuple[set[str], set[str]]:
    """Return `(all_files, ignored_files)` for `root` under a single traversal mode.

    Both sets must come from the same mode, or subtracting one from the other
    compares two different views of the tree.
    """
    ignored_files = {
        p.path for p in spec.match_tree_entries(root, follow_links=follow_links)
    }
    if include_dirs:
        all_files = {
            p.path
            for p in pathspec.util.iter_tree_entries(root, follow_links=follow_links)
        }
    else:
        all_files = set(pathspec.util.iter_tree_files(root, follow_links=follow_links))
    return all_files, ignored_files


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
    spec = pathspec.GitIgnoreSpec.from_lines(ignore_patterns or [])
    try:
        all_files, ignored_files = _walk_tree(root, spec, include_dirs)
    except pathspec.util.RecursionError as exc:
        # A directory symlink pointing at one of its own ancestors makes the
        # default link-following walk revisit the same real directory, and
        # pathspec raises rather than returning the tree. Retry once without
        # following links: symlinks are then listed as entries but not
        # descended into, which is what `git` itself does with the .gitignore
        # specification this function implements. Only this walk changes --
        # a tree with no cycle still follows links as before.
        # Imported here rather than at module scope: this is a cold path, and
        # prefect.logging imports back into prefect.utilities. get_logger
        # rather than logging.getLogger because it installs
        # ObfuscateApiKeyFilter, and these paths come from the user's tree.
        from prefect.logging.loggers import get_logger

        get_logger("utilities.filesystem").warning(
            "Not following symlinks while walking %r: %r and %r both resolve to %r.",
            root,
            exc.first_path or ".",
            exc.second_path,
            exc.real_path,
        )
        all_files, ignored_files = _walk_tree(
            root, spec, include_dirs, follow_links=False
        )
    included_files = all_files - ignored_files

    # Ensure parent directories of included files are also included,
    # so that copytree's ignore_func doesn't skip directories containing
    # files that should be copied.
    if include_dirs:
        parent_dirs: set[str] = set()
        for file_path in included_files:
            for parent in Path(file_path).parents:
                parent_str = str(parent)
                if parent_str == ".":
                    break
                parent_dirs.add(parent_str)
        included_files |= parent_dirs

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
