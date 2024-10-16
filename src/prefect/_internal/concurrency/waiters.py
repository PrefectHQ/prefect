"""
Implementations of `Waiter`s, which allow work to be sent back to a thread while it
waits for the result of the call.
"""

import abc
import asyncio
import contextlib
import inspect
import queue
import threading
from collections import deque
from typing import Awaitable, Generic, List, Optional, TypeVar, Union
from weakref import WeakKeyDictionary

import anyio

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.event_loop import call_soon_in_loop
from prefect._internal.concurrency.primitives import Event

T = TypeVar("T")


# Waiters are stored in a stack for each thread
_WAITERS_BY_THREAD: "WeakKeyDictionary[threading.Thread, deque[Waiter]]" = (
    WeakKeyDictionary()
)


def add_waiter_for_thread(waiter: "Waiter", thread: threading.Thread):
    """
    Add a waiter for a thread.
    """
    if thread not in _WAITERS_BY_THREAD:
        _WAITERS_BY_THREAD[thread] = deque()

    _WAITERS_BY_THREAD[thread].append(waiter)


class Waiter(Portal, abc.ABC, Generic[T]):
    """
    A waiter allows waiting for a call while routing callbacks to the
    the current thread.

    Calls sent back to the waiter will be executed when waiting for the result.
    """

    def __init__(self, call: Call[T]) -> None:
        if not isinstance(call, Call):  # Guard against common mistake
            raise TypeError(f"Expected call of type `Call`; got {call!r}.")

        self._call = call
        self._owner_thread = threading.current_thread()

        # Set the waiter for the current thread
        add_waiter_for_thread(self, self._owner_thread)
        super().__init__()

    def call_is_done(self) -> bool:
        return self._call.future.done()

    @abc.abstractmethod
    def wait(self) -> Union[Awaitable[None], None]:
        """
        Wait for the call to finish.

        Watch for and execute any waiting callbacks.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def add_done_callback(self, callback: Call) -> Call:
        """
        Schedule a call to run when the waiter is done waiting.

        If the waiter is already done, a `RuntimeError` error will be thrown.
        """
        raise NotImplementedError()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} call={self._call},"
            f" owner={self._owner_thread.name!r}>"
        )


class SyncWaiter(Waiter[T]):
    # Implementation of `Waiter` for use in synchronous contexts

    def __init__(self, call: Call[T]) -> None:
        super().__init__(call=call)
        self._queue: queue.Queue = queue.Queue()
        self._done_callbacks = []
        self._done_event = threading.Event()

    def submit(self, call: Call):
        """
        Submit a callback to execute while waiting.
        """
        if self.call_is_done():
            raise RuntimeError(f"The call {self._call} is already done.")

        self._queue.put_nowait(call)
        call.set_runner(self)
        return call

    def _handle_waiting_callbacks(self):
        logger.debug("Waiter %r watching for callbacks", self)
        while True:
            callback: Call = self._queue.get()
            if callback is None:
                break

            # Ensure that callbacks are cancelled if the parent call is cancelled so
            # waiting never runs longer than the call
            self._call.future.add_cancel_callback(callback.future.cancel)
            callback.run()
            del callback

    @contextlib.contextmanager
    def _handle_done_callbacks(self):
        try:
            yield
        finally:
            # Call done callbacks
            while self._done_callbacks:
                callback = self._done_callbacks.pop()
                if callback:
                    callback.run()

    def add_done_callback(self, callback: Call):
        if self._done_event.is_set():
            raise RuntimeError("Cannot add done callbacks to done waiters.")
        else:
            self._done_callbacks.append(callback)

    def wait(self) -> T:
        # Stop watching for work once the future is done
        self._call.future.add_done_callback(lambda _: self._queue.put_nowait(None))
        self._call.future.add_done_callback(lambda _: self._done_event.set())

        with self._handle_done_callbacks():
            self._handle_waiting_callbacks()

            # Wait for the future to be done
            self._done_event.wait()

        _WAITERS_BY_THREAD[self._owner_thread].remove(self)
        return self._call


class AsyncWaiter(Waiter[T]):
    # Implementation of `Waiter` for use in asynchronous contexts

    def __init__(self, call: Call[T]) -> None:
        super().__init__(call=call)

        # Delay instantiating loop and queue as there may not be a loop present yet
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._early_submissions: List[Call] = []
        self._done_callbacks = []
        self._done_event = Event()
        self._done_waiting = False

    def submit(self, call: Call):
        """
        Submit a callback to execute while waiting.
        """
        if self.call_is_done():
            raise RuntimeError(f"The call {self._call} is already done.")

        call.set_runner(self)

        if not self._queue:
            # If the loop is not yet available, just push the call to a stack
            self._early_submissions.append(call)
            return call

        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, call)
        return call

    def _resubmit_early_submissions(self):
        assert self._queue
        for call in self._early_submissions:
            # We must put items in the queue from the event loop that owns it
            call_soon_in_loop(self._loop, self._queue.put_nowait, call)
        self._early_submissions = []

    async def _handle_waiting_callbacks(self):
        logger.debug("Waiter %r watching for callbacks", self)
        tasks = []

        try:
            while True:
                callback: Call = await self._queue.get()
                if callback is None:
                    break

                # Ensure that callbacks are cancelled if the parent call is cancelled so
                # waiting never runs longer than the call
                self._call.future.add_cancel_callback(callback.future.cancel)
                retval = callback.run()
                if inspect.isawaitable(retval):
                    tasks.append(retval)

                del callback

            # Tasks are collected and awaited as a group; if each task was awaited in
            # the above loop, async work would not be executed concurrently
            await asyncio.gather(*tasks)
        finally:
            self._done_waiting = True

    @contextlib.asynccontextmanager
    async def _handle_done_callbacks(self):
        try:
            yield
        finally:
            # Call done callbacks
            while self._done_callbacks:
                callback = self._done_callbacks.pop()
                if callback:
                    # We shield against cancellation so we can run the callback
                    with anyio.CancelScope(shield=True):
                        await self._run_done_callback(callback)

    async def _run_done_callback(self, callback: Call):
        coro = callback.run()
        if coro:
            await coro

    def add_done_callback(self, callback: Call):
        if self._done_event.is_set():
            raise RuntimeError("Cannot add done callbacks to done waiters.")
        else:
            self._done_callbacks.append(callback)

    def _signal_stop_waiting(self):
        # Only send a `None` to the queue if the waiter is still blocked reading from
        # the queue. Otherwise, it's possible that the event loop is stopped.
        if not self._done_waiting:
            call_soon_in_loop(self._loop, self._queue.put_nowait, None)

    async def wait(self) -> Call[T]:
        # Assign the loop
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._resubmit_early_submissions()

        # Stop watching for work once the future is done
        self._call.future.add_done_callback(lambda _: self._signal_stop_waiting())
        self._call.future.add_done_callback(lambda _: self._done_event.set())

        async with self._handle_done_callbacks():
            await self._handle_waiting_callbacks()

            # Wait for the future to be done
            await self._done_event.wait()

        _WAITERS_BY_THREAD[self._owner_thread].remove(self)
        return self._call
