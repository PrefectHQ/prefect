"""
Thread-safe async primitives.
"""

import asyncio
import concurrent.futures
from typing import Any

from prefect._internal.concurrency.event_loop import (
    get_running_loop,
    run_in_loop_thread,
)


class Event:
    """
    A thread-safe async event.
    """

    def __init__(self) -> None:
        self._loop = get_running_loop()

        # For compatibility with Python <3.10, do not create the event until a loop
        # is present
        if self._loop:
            self._event = asyncio.Event()

        self._is_set = False

    def set(self):
        """Set the flag, notifying all listeners."""
        self._is_set = True
        if self._loop:
            if self._loop != get_running_loop():
                return run_in_loop_thread(self._loop, self._event.set)
            else:
                return self._event.set()

    def is_set(self) -> bool:
        """Return ``True`` if the flag is set, ``False`` if not."""
        return self._is_set

    async def wait(self) -> None:
        """
        Wait until the flag has been set.

        If the flag has already been set when this method is called, it returns immediately.
        """
        if self._is_set:
            return

        if not self._loop:
            self._loop = get_running_loop()
            self._event = asyncio.Event()

        return await self._event.wait()

    def __repr__(self) -> str:
        return f"Event<loop={id(self._loop)}, is_set={self._is_set}>"


class Future:
    """
    A thread-safe async future.
    """

    def __init__(self, __sync_future: concurrent.futures.Future = None):
        self._done_event = Event()
        self._future = __sync_future or concurrent.futures.Future()
        self._future.add_done_callback(self._set_done_event)

    def _set_done_event(self, future: "concurrent.futures.Future"):
        assert future is self._future
        self._done_event.set()

    async def result(self):
        """Get the result of the future."""
        await self._done_event.wait()
        return self._future.result(timeout=0)

    def cancel(self) -> bool:
        return self._future.cancel()

    def set_running_or_notify_cancel(self):
        return self._future.set_running_or_notify_cancel()

    def set_result(self, result: Any):
        return self._future.set_result(result)

    def set_exception(self, exception: BaseException):
        return self._future.set_exception(exception)
