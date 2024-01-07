"""
Utilities for Python version compatibility
"""
# Please organize additions to this file by version

import asyncio
import sys
from shutil import copytree
from signal import raise_signal

def destringitize(obj: str) -> object:
    if sys.version_info >= (3, 13):
        return obj
    elif sys.version_info >= (3, 10):
        from inspect import get_annotations
        return get_annotations(obj)
    else:
        raise ValueError("From __future__ import annotations is supported for"
                         " Python versions 3.9+ only with Prefect.")


if sys.version_info < (3, 10):
    import importlib_metadata
    from importlib_metadata import EntryPoint, EntryPoints, entry_points
else:
    import importlib.metadata as importlib_metadata
    from importlib.metadata import EntryPoint, EntryPoints, entry_points

if sys.version_info < (3, 9):
    # https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread

    import functools

    async def asyncio_to_thread(fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

else:
    from asyncio import to_thread as asyncio_to_thread

if sys.platform != "win32":
    from asyncio import ThreadedChildWatcher
