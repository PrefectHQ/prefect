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

from typing_extensions import ParamSpec, Self

from prefect._internal.concurrency.event_loop import (
    call_soon_in_loop,
    get_running_loop,
    in_async_context,
)
from prefect._internal.concurrency.runtime import get_runtime_thread
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


def new_supervisor(
    force_sync: bool = False,
    allow_callbacks: bool = True,
    timeout: Optional[float] = None,
) -> "Supervisor":
    if not force_sync and in_async_context():
        return AsyncSupervisor(allow_callbacks=allow_callbacks, timeout=timeout)
    else:
        return SyncSupervisor(allow_callbacks=allow_callbacks, timeout=timeout)


def call_soon_in_supervising_thread(
    __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> concurrent.futures.Future:
    """
    Call a function in the supervising thread.

    Must be used from a call scheduled by `call_soon_in_worker_thread` or
    `call_soon_in_runtime_thread` or there will not be a supervisor.

    Returns a future.
    """
    current_supervisor = get_supervisor()
    if current_supervisor is None:
        raise RuntimeError("No supervisor found.")

    future = current_supervisor.call_soon_in_supervisor_thread(__fn, *args, **kwargs)
    return future


@dataclasses.dataclass
class _Callback:
    """
    A deferred function call.
    """

    future: concurrent.futures.Future
    fn: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    context: contextvars.Context

    @classmethod
    def from_call(cls, __fn, *args, **kwargs) -> "_Callback":
        return cls(
            future=concurrent.futures.Future(),
            fn=__fn,
            args=args,
            kwargs=kwargs,
            context=contextvars.copy_context(),
        )

    def __post_init__(self):
        logger.debug("Created callback %r", self)

    def run(self):
        """
        Execute the callback.

        All exceptions during execution of the callback are captured and attached to
        the future.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel():
            return

        logger.debug("Running callback %s", self)

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
            logger.debug("Encountered exception in callback %r", self)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)
            logger.debug("Finished callback %r", self)

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
            logger.debug("Encountered exception %s in callback %r", exc, self)
            del self
        else:
            self.future.set_result(result)
            logger.debug("Finished callback %r", self)


class Supervisor(abc.ABC, Generic[T]):
    """
    A supervisor monitors a future.

    Supervisors allows calls to be sent back to the thread that owns the supervisor.
    Supervisors enable robust cancellation of futures.

    Calls sent to the supervisor will be executed when the owner waits for the result.
    """

    def __init__(
        self,
        allow_callbacks: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        self._callbacks_allowed = allow_callbacks
        self._owner_thread = threading.current_thread()
        self._future: Optional[concurrent.futures.Future] = None
        self._future_call: Tuple[Callable, Tuple, Dict] = None
        self._timeout: Optional[float] = timeout

        # Delayed computation
        self._worker_thread_future = concurrent.futures.Future()
        self._deadline_future = concurrent.futures.Future()

        logger.debug("Created supervisor %r", self)

    def submit_with(
        self,
        __submit_fn: Callable[..., concurrent.futures.Future],
        __fn: Callable,
        *args,
        **kwargs,
    ) -> concurrent.futures.Future:
        """
        Submit a call to a worker.

        The supervisor will use the `submit_fn` to send the call to the worker.
        The supervisor will wrap the callable to provide supervision.

        This method may only be called once per supervisor.
        """
        if self._future:
            raise RuntimeError("A supervisor can only monitor a single future")

        with set_supervisor(self):
            future = __submit_fn(self._add_supervision(__fn), *args, **kwargs)

        logger.debug(
            "Call to %r submitted to supervisor %r tracked by future %r",
            __fn.__name__,
            self,
            future,
        )
        self._future = future
        self._future_call = (__fn, args, kwargs)

        return future

    def call_soon_in_supervisor_thread(
        self, __fn, *args, **kwargs
    ) -> concurrent.futures.Future:
        """
        Schedule a call in the supervisor thread from a worker thread.

        Returns the created future.
        """
        callback = _Callback.from_call(__fn, *args, **kwargs)
        self._put_callback(callback)
        logger.debug("Sent callback to supervisor %r", self)
        return callback.future

    def call_soon_in_runtime_thread(
        self: Self, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Self:
        """
        Schedule a coroutine function in the runtime thread.

        Returns the supervisor.
        """
        runtime = get_runtime_thread()
        self.submit_with(runtime.submit_to_loop, __fn, *args, **kwargs)
        return self

    def call_soon_in_worker_thread(
        self: Self, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Self:
        """
        Schedule a function in a worker thread.

        Returns the supervisor.
        """
        runtime = get_runtime_thread()
        self.submit_with(runtime.submit_to_worker_thread, __fn, *args, **kwargs)
        return self

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
            deadline = get_deadline(self._timeout)
            self._deadline_future.set_result(deadline)

            # Enforce timeouts on synchronous execution
            with cancel_sync_after(self._timeout):
                retval = fn(*args, **kwargs)

            # Enforce timeouts on asynchronous execution
            if inspect.isawaitable(retval):

                async def _call_in_supervised_coro():
                    # Here, we use the deadline since time may have elapsed during the
                    # synchronous portion
                    with cancel_async_at(deadline):
                        return await retval

                return _call_in_supervised_coro()

            return retval

        return _call_in_supervised_thread

    @abc.abstractmethod
    def _put_callback(self, callback: _Callback) -> None:
        """
        Add a callback to the supervisor. Used by `call_soon_in_supervisor_thread`.
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
        future = repr(self._future) if self._future else "<not submitted>"
        return (
            f"<{self.__class__.__name__} future={future}, "
            f"owner={self._owner_thread.name!r}>"
        )


class SyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        allow_callbacks: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(allow_callbacks=allow_callbacks, timeout=timeout)
        self._queue: queue.Queue = queue.Queue()

    def result(self) -> T:
        if not self._future:
            raise ValueError("No future being supervised.")

        # Stop watching for work once the future is done
        self._future.add_done_callback(lambda _: self._queue.put_nowait(None))

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

        logger.debug("Supervisor %r retrieving result of future %r", self, self._future)
        return self._future.result()

    def _put_callback(self, callback: _Callback):
        self._queue.put_nowait(callback)

    def _watch_for_callbacks(self):
        """
        Watches for callbacks during `result` retrieval.
        """
        logger.debug("Watching for work sent to supervisor %r", self)
        while True:
            callback: _Callback = self._queue.get()
            if callback is None:
                break

            callback.run()
            del callback


class AsyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        allow_callbacks: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(allow_callbacks=allow_callbacks, timeout=timeout)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    async def result(self) -> T:
        """
        Get the result for the supervised future, watching for callbacks while waiting.

        Returns the result or raises an exception if the future encountered an
        exception.
        """
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
                await self._watch_for_callbacks()
        except TimeoutError:
            # Timeouts will be re-raised on future result retrieval
            if not ctx.cancelled:
                raise

        logger.debug("Supervisor %r retrieving result of future %r", self, future)
        return await future

    def _put_callback(self, callback: _Callback):
        # We must put items in the queue from the event loop that owns it
        call_soon_in_loop(self._loop, self._queue.put_nowait, callback)

    async def _watch_for_callbacks(self):
        """
        Watches for callbacks during `result` retrieval.
        """
        logger.debug("Watching for work sent to %r", self)
        while True:
            callback: _Callback = await self._queue.get()
            if callback is None:
                break

            # TODO: We could use `cancel_sync_after` to guard this call as a sync call
            #       could block a timeout here
            retval = callback.run()

            if inspect.isawaitable(retval):
                await retval

            del callback
