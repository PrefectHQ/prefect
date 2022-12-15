"""
Thread-safe async primitives.
"""
import asyncio
import concurrent.futures
from typing import Generic, Optional, TypeVar

from prefect._internal.concurrency.event_loop import call_in_loop, get_running_loop

T = TypeVar("T")


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

    def set(self) -> None:
        """Set the flag, notifying all listeners."""
        self._is_set = True
        if self._loop:
            if self._loop != get_running_loop():
                call_in_loop(self._loop, self._event.set)
            else:
                self._event.set()

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

        await self._event.wait()

    def __repr__(self) -> str:
        return f"Event<loop={id(self._loop)}, is_set={self._is_set}>"


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
