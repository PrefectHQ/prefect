"""
Utilities for working with file systems
"""
import os
import pathlib
import shutil
import stat
import sys
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Union

import fsspec
import pathspec
from fsspec.core import OpenFile
from fsspec.implementations.local import LocalFileSystem

# Needed for copytree functionality in 3.7
if sys.version_info < (3, 8):
    pass


def set_default_ignore_file(path: str) -> bool:
    """
    Creates default ignore file in the provided path if one does not already exist; returns boolean specifying
    whether a file was created.
    """
    path = pathlib.Path(path)
    if (path / ".prefectignore").exists():
        return False
    default_file = pathlib.Path(__file__).parent / ".." / ".prefectignore"
    with open(path / ".prefectignore", "w") as f:
        f.write(default_file.read_text())
    return True


def filter_files(
    root: str = ".", ignore_patterns: list = None, include_dirs: bool = True
) -> set:
    """
    This function accepts a root directory path and a list of file patterns to ignore, and returns
    a list of files that excludes those that should be ignored.

    The specification matches that of [.gitignore files](https://git-scm.com/docs/gitignore).
    """
    if ignore_patterns is None:
        ignore_patterns = []
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)
    ignored_files = {p.path for p in spec.match_tree_entries(root)}
    if include_dirs:
        all_files = {p.path for p in pathspec.util.iter_tree_entries(root)}
    else:
        all_files = set(pathspec.util.iter_tree_files(root))
    included_files = all_files - ignored_files
    return included_files


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


def relative_path_to_current_platform(path_str: str) -> Path:
    """
    Converts a relative path generated on any platform to a relative path for the
    current platform.
    """

    return Path(PureWindowsPath(path_str).as_posix())


def _copytree_37(src, dst, original_src, symlinks=False, ignore=None):
    """
    Replicates the behavior of `shutil.copytree(src=src, dst=dst, ignore=ignore, dirs_exist_ok=True)`
    in a python 3.7 compatible manner.

    Source for the logic: Cyrille Pontvieux at https://stackoverflow.com/a/22331852
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    elements = os.listdir(src)

    if ignore:
        exclude = ignore(src, elements)
        elements = [el for el in elements if el not in exclude]

    for item in elements:
        source_path = os.path.join(src, item)
        destination_path = os.path.join(dst, item)
        if symlinks and os.path.islink(source_path):
            if os.path.lexists(destination_path):
                os.remove(destination_path)
            os.symlink(os.readlink(source_path), destination_path)
            try:
                st = os.lstat(source_path)
                mode = stat.S_IMODE(st.st_mode)
                os.lchmod(destination_path, mode)
            except:
                pass  # lchmod not available
        elif os.path.isdir(source_path):
            _copytree_37(source_path, destination_path, original_src, symlinks, ignore)
        else:
            shutil.copy2(source_path, destination_path)


def prefect_copytree(src, dst, ignore=None):
    if sys.version_info < (3, 8):
        _copytree_37(src=src, dst=dst, original_src=src, ignore=ignore)
    else:
        shutil.copytree(src=src, dst=dst, ignore=ignore, dirs_exist_ok=True)
