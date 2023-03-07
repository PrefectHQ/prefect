"""
Implementations of `Waiter`s, which allow work to be sent back to a thread while it
waits for the result of the call.
"""

import abc
import asyncio
import inspect
import queue
import threading
from typing import Awaitable, Generic, TypeVar, Union

from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.event_loop import call_soon_in_loop
from prefect._internal.concurrency.timeouts import (
    CancelContext,
    cancel_async_at,
    cancel_sync_at,
)
from prefect.logging import get_logger

T = TypeVar("T")

# TODO: We should update the format for this logger to include the current thread
logger = get_logger("prefect._internal.concurrency.waiters")


class Waiter(Portal, abc.ABC, Generic[T]):
    """
    A waiter allows a waiting for the result of a call while routing callbacks to the
    the current thread.

    Calls sent back to the waiter will be executed when waiting for the result.
    """

    def __init__(self, call: Call[T]) -> None:
        if not isinstance(call, Call):  # Guard against common mistake
            raise TypeError(f"Expected call of type `Call`; got {call!r}.")

        call.set_callback_portal(self)
        self._call = call
        self._owner_thread = threading.current_thread()

        super().__init__()

    @abc.abstractmethod
    def result(self) -> Union[Awaitable[T], T]:
        """
        Retrieve the result of the call.

        Watch for and execute any callbacks.
        """
        raise NotImplementedError()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} call={self._call},"
            f" owner={self._owner_thread.name!r}>"
        )


class SyncWaiter(Waiter[T]):
    def __init__(self, call: Call[T]) -> None:
        super().__init__(call=call)
        self._queue: queue.Queue = queue.Queue()

    def submit(self, call: Call):
        """
        Submit a callback to execute while waiting.
        """
        self._queue.put_nowait(call)
        call.set_portal(self)
        return call

    def _watch_for_callbacks(self, cancel_context: CancelContext):
        logger.debug("Watching for work sent to waiter %r", self)
        while True:
            callback: Call = self._queue.get()
            if callback is None:
                break

            # We could set the deadline for the callback to match the call we are
            # waiting for, but callbacks can have their own timeout and we don't want to
            # override it
            cancel_context.chain(callback.cancel_context)
            callback.run()
            del callback

    def result(self) -> T:
        # Stop watching for work once the future is done
        self._call.future.add_done_callback(lambda _: self._queue.put_nowait(None))

        # Cancel work sent to the waiter if the future exceeds its timeout
        try:
            with cancel_sync_at(self._call.cancel_context.deadline) as ctx:
                self._watch_for_callbacks(ctx)
        except TimeoutError:
            # Timeouts will be generally be raised on future result retrieval but
            # if its not our timeout it should be reraised
            if not ctx.cancelled():
                raise

        logger.debug(
            "Waiter %r retrieving result of future %r", self, self._call.future
        )
        return self._call.future.result()


class AsyncWaiter(Waiter[T]):
    def __init__(self, call: Call[T]) -> None:
        super().__init__(call=call)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def submit(self, call: Call):
        """
        Submit a callback to execute while waiting.
        """
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, call)
        call.set_portal(self)
        return call

    async def _watch_for_callbacks(self, cancel_context: CancelContext):
        logger.debug("Watching for work sent to %r", self)
        tasks = []

        while True:
            callback: Call = await self._queue.get()
            if callback is None:
                break

            # We could set the deadline for the callback to match the call we are
            # waiting for, but callbacks can have their own timeout and we don't want to
            # override it
            cancel_context.chain(callback.cancel_context)
            retval = callback.run()
            if inspect.isawaitable(retval):
                tasks.append(retval)

            del callback

        # Tasks are collected and awaited as a group; if each task was awaited in the
        # above loop, async work would not be executed concurrently
        await asyncio.gather(*tasks)

    async def result(self) -> T:
        # Wrap the future for a non-blocking wait
        future = asyncio.wrap_future(self._call.future)

        # Stop watching for work once the future is done
        future.add_done_callback(
            lambda _: call_soon_in_loop(self._loop, self._queue.put_nowait, None)
        )

        # Cancel work sent to the waiter if the future exceeds its timeout
        try:
            with cancel_async_at(self._call.cancel_context.deadline) as ctx:
                await self._watch_for_callbacks(ctx)
        except TimeoutError:
            # Timeouts will be re-raised on future result retrieval
            if not ctx.cancelled():
                raise

        logger.debug("Waiter %r retrieving result of future %r", self, future)
        return await future
