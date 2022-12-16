"""
Thread-safe async primitives.
"""
import asyncio
import collections
import concurrent.futures
import threading
from typing import Generic, Optional, TypeVar

from typing_extensions import Literal

from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop

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
        self._waiters = collections.deque()
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

            fut = asyncio.get_running_loop().create_future()
            self._waiters.append(fut)

        try:
            await fut
            return True
        finally:
            self._waiters.remove(fut)


class Future(concurrent.futures.Future, Generic[T]):
    """
    A thread-safe async future.

    See `concurrent.futures.Future` documentation for details.
        https://docs.python.org/3/library/concurrent.futures.html#future-objects

    This implemention adds an `aresult` method to wait for results asynchronously.
    """

    def __init__(self):
        super().__init__()
        self._attach_async_callback()

    def _attach_async_callback(self):
        self._done_event = Event()
        self.add_done_callback(self._set_done_event)

    def _set_done_event(self, _: "concurrent.futures.Future") -> None:
        self._done_event.set()

    def result(self: "Future[T]", timeout: Optional[float] = None) -> T:
        if get_running_loop() is not None:
            raise RuntimeError(
                "Future.result() cannot be called from an async thread; "
                "use `aresult()` instead to avoid blocking the event loop."
            )
        return super().result(timeout)

    async def aresult(self: "Future[T]") -> T:
        """
        Wait for the result from the future and return it.

        If the future encountered an exception, it will be raised.
        """
        await self._done_event.wait()
        return super().result(timeout=0)

    @classmethod
    def from_existing(cls, future: "concurrent.futures.Future") -> "Future":
        """
        Create an async future from an existing future.
        """
        new = cls.__new__(cls)
        new.__dict__ = future.__dict__
        new._attach_async_callback()
        return new
