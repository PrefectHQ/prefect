"""
Thread-safe async synchronization primitives.
"""

import asyncio
import collections
import threading
from typing import TypeVar

from typing_extensions import Literal

from prefect._internal.concurrency.event_loop import call_soon_in_loop

T = TypeVar("T")


class Event:
    """
    A thread-safe async event.

    Unlike `asyncio.Event` this implementation does not bind to a loop on creation. This
    matches the behavior of `asyncio.Event` in Python 3.10+, but differs from earlier
    versions.

    This event also does not support a `clear()` operation. This matches the behavior of
    `anyio.Event` types and prevents sneaky bugs; create a new event instead.
    """

    def __init__(self) -> None:
        self._waiters: collections.deque[asyncio.Future[bool]] = collections.deque()
        self._value = False
        self._lock = threading.Lock()

    def set(self) -> None:
        """
        Set the flag, notifying all waiters.

        Unlike `asyncio.Event`, waiters may not be notified immediately when this is
        called; instead, notification will be placed on the owning loop of each waiter
        for thread safety.
        """
        with self._lock:
            if not self._value:
                self._value = True

                # We freeze the waiters queue during iteration so removal in `wait()`
                # does not change the size during iteration. The lock ensures that no
                # waiters are added until after we finish here.
                for fut in tuple(self._waiters):
                    if not fut.done():
                        # The `asyncio.Future.set_result` method is not thread-safe
                        # and must be run in the loop that owns the future
                        call_soon_in_loop(fut._loop, fut.set_result, True)

    def is_set(self):
        return self._value

    async def wait(self) -> Literal[True]:
        """
        Block until the internal flag is true.

        If the internal flag is true on entry, return True immediately.
        Otherwise, block until another `set()` is called, then return True.
        """
        # Taking a sync lock in an async context is generally not recommended, but this
        # lock should only ever be held very briefly and we need to prevent race
        # conditions during between `set()` and `wait()`
        with self._lock:
            if self._value:
                return True

            fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            self._waiters.append(fut)

        try:
            await fut
            return True
        finally:
            self._waiters.remove(fut)
