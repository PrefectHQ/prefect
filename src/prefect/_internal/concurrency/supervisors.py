"""
Implementations of supervisors for futures, which allow work to be sent back to the
thread waiting for the result of the future.
"""

import abc
import asyncio
import concurrent.futures
import contextlib
import contextvars
import functools
import inspect
import queue
import threading
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.event_loop import call_soon_in_loop
from prefect._internal.concurrency.portals import Call, Portal
from prefect._internal.concurrency.timeouts import (
    cancel_async_at,
    cancel_sync_after,
    cancel_sync_at,
    get_deadline,
)
from prefect.logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")
Fn = TypeVar("Fn", bound=Callable)

# Python uses duck typing for futures; asyncio/threaded futures do not share a base
AnyFuture = Any

# TODO: We should update the format for this logger to include the current thread
logger = get_logger("prefect._internal.concurrency.supervisors")

# Tracks the current supervisor managed by `set_supervisor`
current_supervisor: contextvars.ContextVar["Supervisor"] = contextvars.ContextVar(
    "current_supervisor"
)


def get_supervisor() -> Optional["Supervisor"]:
    return current_supervisor.get(None)


@contextlib.contextmanager
def set_supervisor(supervisor: "Supervisor"):
    token = current_supervisor.set(supervisor)
    try:
        yield
    finally:
        current_supervisor.reset(token)


class Supervisor(Portal, abc.ABC, Generic[T]):
    """
    A supervisor monitors a call running on another thread and allows work to be sent
    back to its own thread.

    Calls sent to the supervisor will be executed when waiting for the result.
    """

    def __init__(
        self,
        call: Call[T],
        portal: Portal,
        timeout: Optional[float] = None,
    ) -> None:
        if not isinstance(call, Call):  # Guard against common mistake
            raise TypeError(f"Expected call of type `Call`; got {call!r}.")

        self._call = self._wrap_supervised_call(call)
        self._portal = portal
        self._owner_thread = threading.current_thread()
        self._timeout: Optional[float] = timeout

        # When the call starts, it will set a deadline
        self._deadline_future = concurrent.futures.Future()

        logger.debug("Created supervisor %r", self)

    def start(self):
        """
        Start the supervisor by submitting the call to the portal.
        """
        self._portal.submit(self._call)

    def submit(self, call: Call) -> Call:
        """
        Submit a call to the supervisor work queue from another thread.

        Returns the call.
        """
        self._put_call_in_queue(call)
        logger.debug("Sent call back to supervisor %r", self)
        return call

    @abc.abstractmethod
    def result(self) -> Union[Awaitable[T], T]:
        """
        Retrieve the result of the supervised call.

        Watch for and execute any work sent back.
        """
        raise NotImplementedError()

    def shutdown(self):
        # A supervisor does nothing on shutdown
        pass

    @property
    def name(self):
        return self._owner_thread.name

    def _wrap_supervised_call(self, call: Call) -> Call:
        """
        Wrap a call with supervision.
        """

        def get_updated_context():
            # Update the call context to include this supervisor
            with set_supervisor(self):
                return contextvars.copy_context()

        return Call(
            future=call.future,
            fn=self._add_supervision(call.fn),
            args=call.args,
            kwargs=call.kwargs,
            context=call.context.run(get_updated_context),
        )

    def _add_supervision(self, fn: Fn) -> Fn:
        """
        Attach supervision to a callable.
        """

        @functools.wraps(fn)
        def _call_in_supervised_thread(*args, **kwargs):
            # Set the execution deadline
            deadline = get_deadline(self._timeout)
            self._deadline_future.set_result(deadline)

            # Enforce timeouts on synchronous execution
            with cancel_sync_after(self._timeout):
                retval = fn(*args, **kwargs)

            # Enforce timeouts on asynchronous execution
            if inspect.isawaitable(retval):

                async def _call_in_supervised_coro():
                    with cancel_async_at(deadline):
                        return await retval

                return _call_in_supervised_coro()

            return retval

        return _call_in_supervised_thread

    @abc.abstractmethod
    def _put_call_in_queue(self, call: Call) -> None:
        """
        Add a call to the supervisor. Used by `send_call`.
        """
        raise NotImplementedError()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} call={self._call},"
            f" portal={self._portal.name!r},"
            f" owner={self._owner_thread.name!r}>"
        )


class SyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        call: Call[T],
        portal: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(call=call, portal=portal, timeout=timeout)
        self._queue: queue.Queue = queue.Queue()

    def _put_call_in_queue(self, callback: Call):
        self._queue.put_nowait(callback)

    def _watch_for_callbacks(self):
        logger.debug("Watching for work sent to supervisor %r", self)
        while True:
            callback: Call = self._queue.get()
            if callback is None:
                break

            callback.run()
            del callback

    def result(self) -> T:
        # Stop watching for work once the future is done
        self._call.future.add_done_callback(lambda _: self._queue.put_nowait(None))

        # Cancel work sent to the supervisor if the future exceeds its timeout
        deadline = self._deadline_future.result()
        try:
            with cancel_sync_at(deadline) as ctx:
                self._watch_for_callbacks()
        except TimeoutError:
            # Timeouts will be generally be raised on future result retrieval but
            # if its not our timeout it should be reraised
            if not ctx.cancelled:
                raise

        logger.debug(
            "Supervisor %r retrieving result of future %r", self, self._call.future
        )
        return self._call.future.result()


class AsyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        call: Call[T],
        portal: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(call=call, portal=portal, timeout=timeout)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def _put_call_in_queue(self, callback: Call):
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, callback)

    async def _watch_for_callbacks(self):
        logger.debug("Watching for work sent to %r", self)
        tasks = []

        while True:
            callback: Call = await self._queue.get()
            if callback is None:
                break

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

        # Cancel work sent to the supervisor if the future exceeds its timeout
        deadline = await asyncio.wrap_future(self._deadline_future)
        try:
            with cancel_async_at(deadline) as ctx:
                await self._watch_for_callbacks()
        except TimeoutError:
            # Timeouts will be re-raised on future result retrieval
            if not ctx.cancelled:
                raise

        logger.debug("Supervisor %r retrieving result of future %r", self, future)
        return await future
