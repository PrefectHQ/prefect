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
import functools
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
from prefect._internal.concurrency.timeouts import (
    cancel_async_after,
    cancel_async_at,
    cancel_sync_after,
    cancel_sync_at,
    get_deadline,
)
from prefect.logging import get_logger

T = TypeVar("T")
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
            logger.debug("Encountered exception in work item %r", self)
            # Prevent reference cycle in `exc`
            del self
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
            logger.debug("Encountered exception %s in work item %r", exc, self)
            del self
        else:
            self.future.set_result(result)
            logger.debug("Finished work item %r", self)


class Supervisor(abc.ABC, Generic[T]):
    """
    A supervisor allows work to be sent back to the thread that owns the supervisor.

    Work sent to the supervisor will be executed when the owner waits for the result.
    """

    def __init__(
        self,
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        self._submit_fn = submit_fn
        self._owner_thread = threading.current_thread()
        self._future: Optional[concurrent.futures.Future] = None
        self._future_call: Tuple[Callable, Tuple, Dict] = None
        self._timeout: Optional[float] = timeout

        # Delayed computation
        self._worker_thread_future = concurrent.futures.Future()
        self._deadline_future = concurrent.futures.Future()

        logger.debug("Created supervisor %r", self)

    def submit(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        """
        Submit a call to a worker.

        The supervisor will use the `submit_fn` from initialization to send the call to
        the worker. It will wrap the call to provide supervision.

        This method may only be called once per supervisor.
        """
        if self._future:
            raise RuntimeError("A supervisor can only monitor a single future")

        with set_supervisor(self):
            future = self._submit_fn(self._add_supervision(__fn), *args, **kwargs)

        logger.debug(
            "Call to %r submitted to supervisor %r tracked by future %r",
            __fn.__name__,
            self,
            future,
        )
        self._future = future
        self._future_call = (__fn, args, kwargs)

        return future

    def send_call_to_supervisor(
        self, __fn, *args, **kwargs
    ) -> concurrent.futures.Future:
        """
        Send a call to the supervisor thread from a worker thread.
        """
        work_item = WorkItem.from_call(__fn, *args, **kwargs)
        self._put_work_item(work_item)
        logger.debug("Sent work item to supervisor %r", self)
        return work_item.future

    @property
    def owner_thread(self):
        return self._owner_thread

    def _add_supervision(self, fn: Fn) -> Fn:
        """
        Attach supervision to a callable.
        """

        @functools.wraps(fn)
        def _call_in_supervised_thread(*args, **kwargs):
            # Capture the worker thread before running the function
            thread = threading.current_thread()
            self._worker_thread_future.set_result(thread)

            # Set the execution deadline
            self._deadline_future.set_result(get_deadline(self._timeout))

            # Enforce timeouts on synchronous execution
            with cancel_sync_after(self._timeout):
                retval = fn(*args, **kwargs)

            # Enforce timeouts on asynchronous execution
            if inspect.isawaitable(retval):

                async def _call_in_supervised_coro():
                    # TODO: Technnically, this should use the deadline but it is not
                    #       clear how to mix sync/async deadlines yet
                    with cancel_async_after(self._timeout):
                        return await retval

                return _call_in_supervised_coro()

            return retval

        return _call_in_supervised_thread

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
        extra = ""

        if self._future_call:
            extra += f" submitted={self._future_call[0].__name__!r},"

        return (
            f"<{self.__class__.__name__} submit_fn={self._submit_fn.__name__!r},"
            f"{extra} owner={self._owner_thread.name!r}>"
        )


class SyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(submit_fn=submit_fn, timeout=timeout)
        self._queue: queue.Queue = queue.Queue()

    def _put_work_item(self, work_item: WorkItem):
        self._queue.put_nowait(work_item)

    def _watch_for_work_items(self):
        logger.debug("Watching for work sent to supervisor %r", self)
        while True:
            work_item: WorkItem = self._queue.get()
            if work_item is None:
                break

            work_item.run()
            del work_item

    def result(self) -> T:
        if not self._future:
            raise ValueError("No future being supervised.")

        # Stop watching for work once the future is done
        self._future.add_done_callback(lambda _: self._queue.put_nowait(None))

        # Cancel work sent to the supervisor if the future exceeds its timeout
        deadline = self._deadline_future.result()
        try:
            with cancel_sync_at(deadline) as ctx:
                self._watch_for_work_items()
        except TimeoutError:
            # Timeouts will be generally be raised on future result retrieval but
            # if its not our timeout it should be reraised
            if not ctx.cancelled:
                raise

        logger.debug("Supervisor %r retrieving result of future %r", self, self._future)
        return self._future.result()


class AsyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(submit_fn=submit_fn, timeout=timeout)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def _put_work_item(self, work_item: WorkItem):
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, work_item)

    async def _watch_for_work_items(self):
        logger.debug("Watching for work sent to %r", self)
        while True:
            work_item: WorkItem = await self._queue.get()
            if work_item is None:
                break

            # TODO: We could use `cancel_sync_after` to guard this call as a sync call
            #       could block a timeout here
            retval = work_item.run()

            if inspect.isawaitable(retval):
                await retval

            del work_item

    async def result(self) -> T:
        if not self._future:
            raise ValueError("No future being supervised.")

        future = (
            # Convert to an asyncio future if necessary for non-blocking wait
            asyncio.wrap_future(self._future)
            if isinstance(self._future, concurrent.futures.Future)
            else self._future
        )

        # Stop watching for work once the future is done
        future.add_done_callback(
            lambda _: call_soon_in_loop(self._loop, self._queue.put_nowait, None)
        )

        # Cancel work sent to the supervisor if the future exceeds its timeout
        deadline = await asyncio.wrap_future(self._deadline_future)
        try:
            with cancel_async_at(deadline) as ctx:
                await self._watch_for_work_items()
        except TimeoutError:
            # Timeouts will be re-raised on future result retrieval
            if not ctx.cancelled:
                raise

        logger.debug("Supervisor %r retrieving result of future %r", self, future)
        return await future
