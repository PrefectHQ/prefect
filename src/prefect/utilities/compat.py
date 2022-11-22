"""
Utilities for Python version compatibility
"""
# Please organize additions to this file by version

import shutil
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import EntryPoint, EntryPoints, entry_points
else:
    from importlib.metadata import EntryPoint, EntryPoints, entry_points

if sys.version_info < (3, 9):
    # https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread

    import asyncio
    import functools

    async def asyncio_to_thread(fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

else:
    from asyncio import to_thread as asyncio_to_thread

if sys.version_info < (3, 8):

    def copytree(src, dst, symlinks=False, ignore=None, *args, **kwargs):
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
                copytree(source_path, destination_path, symlinks, ignore)
            else:
                shutil.copy2(source_path, destination_path)

else:
    from shutil import copytree

if sys.version_info < (3, 8):

    def raise_signal(signal: int):
        os.kill(os.getpid(), signal)

else:
    from signal import raise_signal

if sys.version_info < (3, 8) and sys.platform != "win32":
    # https://docs.python.org/3/library/asyncio-policy.html#asyncio.ThreadedChildWatcher
    # `ThreadedChildWatcher` is the default child process watcher for Python 3.8+ but it
    # does not exist in Python 3.7. This backport allows us to ensure consistent
    # behavior when spawning async child processes without dropping support for 3.7.

    import asyncio
    import itertools
    import logging
    import os
    import threading
    import time
    import warnings

    logger = logging.getLogger()

    # Python 3.7 preferred API
    _get_running_loop = getattr(asyncio, "get_running_loop", asyncio.get_event_loop)

    class ThreadedChildWatcher(asyncio.AbstractChildWatcher):
        def __init__(self):
            self._pid_counter = itertools.count(0)
            self._threads = {}

        def is_active(self):
            return True

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def __del__(self, _warn=warnings.warn):
            threads = [t for t in list(self._threads.values()) if t.is_alive()]
            if threads:
                _warn(
                    f"{self.__class__} has registered but not finished child processes",
                    ResourceWarning,
                    source=self,
                )

        def add_child_handler(self, pid, callback, *args):
            loop = _get_running_loop()
            thread = threading.Thread(
                target=self._do_waitpid,
                name=f"waitpid-{next(self._pid_counter)}",
                args=(loop, pid, callback, args),
                daemon=True,
            )
            self._threads[pid] = thread
            thread.start()

        def remove_child_handler(self, pid):
            # asyncio never calls remove_child_handler() !!!
            # The method is no-op but is implemented because
            # abstract base class requires it
            return True

        def attach_loop(self, loop):
            pass

        def _do_waitpid(self, loop, expected_pid, callback, args):
            assert expected_pid > 0

            try:
                pid, status = os.waitpid(expected_pid, 0)
            except ChildProcessError:
                # The child process is already reaped
                # (may happen if waitpid() is called elsewhere).
                pid = expected_pid
                returncode = 255
                logger.warning(
                    "Unknown child process pid %d, will report returncode 255", pid
                )
            else:
                if os.WIFSIGNALED(status):
                    returncode = -os.WTERMSIG(status)
                elif os.WIFEXITED(status):
                    returncode = os.WEXITSTATUS(status)
                else:
                    returncode = status

                if loop.get_debug():
                    logger.debug(
                        "process %s exited with returncode %s", expected_pid, returncode
                    )

            if loop.is_closed():
                logger.warning("Loop %r that handles pid %r is closed", loop, pid)
            else:
                loop.call_soon_threadsafe(callback, pid, returncode, *args)

            self._threads.pop(expected_pid)

elif sys.platform != "win32":
    from asyncio import ThreadedChildWatcher
