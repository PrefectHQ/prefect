"""
Implementations of supervisors for futures, which allow work to be sent back to the
thread waiting for the result of the future.
"""

import abc
import asyncio
import concurrent.futures
import contextlib
import contextvars
import dataclasses
import inspect
import queue
import threading
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop
from prefect.logging import get_logger

T = TypeVar("T")

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


@dataclasses.dataclass
class WorkItem:
    """
    A deferred function call.
    """

    future: concurrent.futures.Future
    fn: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    context: contextvars.Context

    @classmethod
    def from_call(cls, __fn, *args, **kwargs) -> "WorkItem":
        return cls(
            future=concurrent.futures.Future(),
            fn=__fn,
            args=args,
            kwargs=kwargs,
            context=contextvars.copy_context(),
        )

    def __post_init__(self):
        logger.debug("Created work item %r", self)

    def run(self):
        """
        Execute the work item.

        All exceptions during execution of the work item are captured and attached to
        the future.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel():
            return

        logger.debug("Running work item %s", self)

        # Execute the work and set the result on the future
        if inspect.iscoroutinefunction(self.fn):
            if get_running_loop():
                # If an event loop is available, return a coroutine to be awaited
                return self._run_async()
            else:
                # Otherwise, execute the function here
                return asyncio.run(self._run_async())
        else:
            return self._run_sync()

    def _run_sync(self):
        try:
            result = self.context.run(self.fn, *self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)

        logger.debug("Finished work item %r", self)

    async def _run_async(self):
        loop = asyncio.get_running_loop()
        try:
            # Call the function in the context; this is not necessary if the function
            # is a standard cortouine function but if it's a synchronous function that
            # returns a coroutine we want to ensure the correct context is available
            coro = self.context.run(self.fn, *self.args, **self.kwargs)

            # Run the coroutine in a new task to run with the correct async context
            task = self.context.run(loop.create_task, coro)
            result = await task

        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)

        logger.debug("Finished work item %r", self)


class Supervisor(abc.ABC, Generic[T]):
    """
    A supervisor allows work to be sent back to the thread that owns the supervisor.

    Work sent to the supervisor will be executed when the owner waits for the result.
    """

    def __init__(self) -> None:
        self.owner_thread_ident = threading.get_ident()
        self._future: AnyFuture = None
        logger.debug("Created supervisor %r", self)

    def set_future(self, future: AnyFuture) -> None:
        """
        Assign a future to the supervisor.
        """
        self._future = future

    def send_call(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        """
        Send a call to the supervisor from a worker.
        """
        work_item = WorkItem.from_call(__fn, *args, **kwargs)
        self._put_work_item(work_item)
        logger.debug("Sent work item to %r", self)
        return work_item.future

    @abc.abstractmethod
    def _put_work_item(self, work_item: WorkItem) -> None:
        """
        Add a work item to the supervisor. Used by `send_call`.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def result(self) -> Union[Awaitable[T], T]:
        """
        Retrieve the result of the supervised future.

        Watch for and execute any work sent back.
        """
        raise NotImplementedError()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}(id={id(self)},"
            f" owner={self.owner_thread_ident})>"
        )


class SyncSupervisor(Supervisor[T]):
    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self._future: Optional[concurrent.futures.Future] = None

    def _put_work_item(self, work_item: WorkItem):
        self._queue.put_nowait(work_item)

    def set_future(self, future: concurrent.futures.Future):
        future.add_done_callback(lambda _: self._queue.put_nowait(None))
        super().set_future(future)

    def result(self) -> T:
        if not self._future:
            raise ValueError("No future being supervised.")

        while True:
            logger.debug("Watching for work sent to %r", self)
            work_item: WorkItem = self._queue.get()
            if work_item is None:
                break

            work_item.run()
            del work_item

        logger.debug("Retrieving result for %r", self)
        return self._future.result()


class AsyncSupervisor(Supervisor[T]):
    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._future: Optional[asyncio.Future] = None

    def set_future(
        self, future: Union[asyncio.Future, concurrent.futures.Future]
    ) -> None:
        # Ensure we're working with an asyncio future internally
        if isinstance(future, concurrent.futures.Future):
            future = asyncio.wrap_future(future)

        future.add_done_callback(
            lambda _: call_soon_in_loop(self._loop, self._queue.put_nowait, None)
        )
        super().set_future(future)

    def _put_work_item(self, work_item: WorkItem):
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, work_item)

    async def result(self) -> T:
        if not self._future:
            raise ValueError("No future being supervised.")

        while True:
            logger.debug("Watching for work sent to %r", self)
            work_item: WorkItem = await self._queue.get()
            if work_item is None:
                break

            result = work_item.run()
            if inspect.isawaitable(result):
                await result

            del work_item

        logger.debug("Retrieving result for %r", self)
        return await self._future
