"""
Future implementations
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
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple, TypeVar

from typing_extensions import Self

from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop
from prefect.logging import get_logger

T = TypeVar("T")

logger = get_logger("prefect._internal.concurrency.futures")
current_future = contextvars.ContextVar("current_future")


def get_current_future() -> Optional["WatchingFuture"]:
    return current_future.get(None)


@contextlib.contextmanager
def set_current_future(watcher: "WatchingFuture"):
    token = current_future.set(watcher)
    try:
        yield
    finally:
        current_future.reset(token)


@dataclasses.dataclass
class WorkItem:
    """
    Transport of a deferred function call.
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


class WatchingFuture(abc.ABC):
    """
    A watching future allows work to be sent back to the thread that owns the future by
    the call the future represents.

    Work sent back to the thread will be executed when the owner waits for the result
    of the future.
    """

    def __init__(self) -> None:
        self.owner_thread_ident = threading.get_ident()
        logger.debug("Created future %r", self)

    def wrap_future(self: Self, future) -> Self:
        asyncio.futures._chain_future(future, self)
        return self

    def send_call(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        work_item = WorkItem.from_call(__fn, *args, **kwargs)
        self._put_work_item(work_item)
        logger.debug("Sent work item to %r", self)
        return work_item.future

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={id(self)}, owner={self.owner_thread_ident})>"


class SyncWatchingFuture(WatchingFuture, concurrent.futures.Future):
    def __init__(self) -> None:
        super().__init__()
        concurrent.futures.Future.__init__(self)
        self.queue = queue.Queue()
        self.add_done_callback(lambda fut: fut.queue.put_nowait(None))

    def _put_work_item(self, work_item: WorkItem):
        self.queue.put_nowait(work_item)

    def result(self):
        while True:
            logger.debug("Watching for work sent to %r", self)
            work_item: WorkItem = self.queue.get()
            if work_item is None:
                break

            work_item.run()
            del work_item

        logger.debug("Retrieving result for %r", self)
        return super().result()


class AsyncWatchingFuture(WatchingFuture, asyncio.Future):
    def __init__(self) -> None:
        super().__init__()
        asyncio.Future.__init__(self)
        self.queue = asyncio.Queue()
        self.add_done_callback(
            lambda fut: call_soon_in_loop(fut._loop, fut.queue.put_nowait(None))
        )

    def _put_work_item(self, work_item: WorkItem):
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self.queue.put_nowait, work_item)

    async def result(self):
        while True:
            logger.debug("Watching for work sent to %r", self)
            work_item: WorkItem = await self.queue.get()
            if work_item is None:
                break

            result = work_item.run()
            if isinstance(result, Coroutine):
                await result

            del work_item

        logger.debug("Retrieving result for %r", self)
        return await self
