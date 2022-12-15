"""
Thread-safe async primitives.
"""
import asyncio
import concurrent.futures
from typing import Generic, Optional, TypeVar

from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop

T = TypeVar("T")


class Event(asyncio.Event):
    """
    A thread-safe async event.

    Unlike `asyncio.Event`, this event is bound to an event loop on creation and must
    be instantiated in a running event loop. This matches Python behavior in before
    3.10.
    """

    def __init__(self) -> None:
        super().__init__()
        self._loop = asyncio.get_running_loop()
        self._is_set = False

    def set(self) -> None:
        """
        Set the flag, notifying all listeners.

        Unlike `asyncio.Event`, listeners may not be notified immediately when this is
        called; instead, notification will be placed on the event loop.
        """
        if not self._is_set:
            # Immediately set the flag to true
            # This implementation tracks the value of the event with `_is_set` but the
            # parent class uses `_value`. We need a separate variable because if we set
            # `_value` now, the delayed `set()` call will do nothing.
            self._is_set = True

            # Ask the loop to notify its listeners in the future
            call_soon_in_loop(self._loop, super().set)

    def is_set(self) -> bool:
        return self._is_set


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
