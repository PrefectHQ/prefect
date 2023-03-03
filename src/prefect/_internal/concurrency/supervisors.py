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

from typing_extensions import ParamSpec

from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop
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


@dataclasses.dataclass
class Call(Generic[T]):
    """
    A deferred function call.
    """

    future: concurrent.futures.Future
    fn: Callable[..., T]
    args: Tuple
    kwargs: Dict[str, Any]
    context: contextvars.Context

    @classmethod
    def new(cls, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> "Call[T]":
        return cls(
            future=concurrent.futures.Future(),
            fn=__fn,
            args=args,
            kwargs=kwargs,
            context=contextvars.copy_context(),
        )

    def run(self) -> None:
        """
        Execute the call and place the result on the future.

        All exceptions during execution of the call are captured.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel():
            logger.debug("Skipping execution of cancelled callback %s", self)
            return

        logger.debug("Running callback %s", self)

        coro = self._run_sync()
        if coro is not None:
            loop = get_running_loop()
            if loop:
                # If an event loop is available, return a task to be awaited
                return self.context.run(loop.create_task, self._run_async(coro))
            else:
                # Otherwise, execute the function here
                return self.context.run(asyncio.run, self._run_async(coro))

        return None

    def _run_sync(self):
        try:
            result = self.context.run(self.fn, *self.args, **self.kwargs)

            # Return the coroutine for async execution
            if inspect.isawaitable(result):
                return result

        except BaseException as exc:
            self.future.set_exception(exc)
            logger.debug("Encountered exception in callback %r", self)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)
            logger.debug("Finished callback %r", self)

    async def _run_async(self, coro):
        # When using `loop.create_task`, interrupts are thrown in the event loop
        # instead of being sent back to the task handle so we must wrap the coroutine
        # with another that eats up the exception
        # ref https://github.com/python/cpython/blob/4e7c0cbf59595714848cf9827f6e5b40c3985924/Lib/asyncio/events.py#L85-L86

        try:
            result = await coro
        except BaseException as exc:
            self.future.set_exception(exc)
            logger.debug("Encountered exception %s in call %r", exc, self)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)
            logger.debug("Finished call %r", self)

    def __call__(self) -> T:
        """
        Execute the call and return its result.

        All executions during excecution of the call are re-raised.
        """
        coro = self.run()

        # Return an awaitable if in an async context
        if coro is not None:

            async def run_and_return_result():
                await coro
                return self.future.result()

            return run_and_return_result()
        else:
            return self.future.result()

    def __repr__(self) -> str:
        name = getattr(self.fn, "__name__", str(self.fn))
        call_args = ", ".join(
            [repr(arg) for arg in self.args]
            + [f"{key}={repr(val)}" for key, val in self.kwargs.items()]
        )

        # Enforce a maximum length
        if len(call_args) > 100:
            call_args = call_args[:100] + "..."

        return f"{name}({call_args})"

    def __post_init__(self):
        logger.debug("Created call %r", self)


class Supervisor(abc.ABC, Generic[T]):
    """
    A supervisor allows work to be sent back to the thread that owns the supervisor.

    Work sent to the supervisor will be executed when the owner waits for the result.
    """

    def __init__(
        self,
        call: Call[T],
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        if not isinstance(call, Call):
            # This is a common mistake
            raise TypeError(f"Expected call of type `Call`; got {call!r}.")

        self._call = call
        self._submit_fn = submit_fn
        self._owner_thread = threading.current_thread()
        self._future: Optional[concurrent.futures.Future] = None
        self._future_call: Tuple[Callable, Tuple, Dict] = None
        self._timeout: Optional[float] = timeout

        # Delayed computation
        self._worker_thread_future = concurrent.futures.Future()
        self._deadline_future = concurrent.futures.Future()

        logger.debug("Created supervisor %r", self)

    def submit(self) -> concurrent.futures.Future:
        """
        Submit the call to the worker.

        The supervisor will use the `submit_fn` from initialization to send the call to
        the worker. It will wrap the call to provide supervision.

        This method may only be called once per supervisor.
        """
        if self._future:
            raise RuntimeError("A supervisor's call can only be submitted once.")

        with set_supervisor(self):
            future = self._submit_fn(
                self._add_supervision(self._call.fn),
                *self._call.args,
                **self._call.kwargs,
            )

        self._future = future
        logger.debug("Call for supervisor %r submitted", self)

        return future

    def send_call_to_supervisor(self, call: Call) -> concurrent.futures.Future:
        """
        Send a call to the supervisor thread from a worker thread.
        """
        self.put_call(call)
        logger.debug("Sent call back to supervisor %r", self)
        return call.future

    def submit_to_supervisor(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        """
        Submit a function call to the supervisor thread from a worker thread.
        """
        call = Call.new(__fn, *args, **kwargs)
        return self.send_call_to_supervisor(call)

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

            # Add supervision to returned coroutines
            if inspect.isawaitable(retval):

                async def _call_in_supervised_coro():
                    # Enforce timeouts on asynchronous execution
                    with cancel_async_at(deadline):
                        return await retval

                return _call_in_supervised_coro()

            return retval

        return _call_in_supervised_thread

    @abc.abstractmethod
    def put_call(self, call: Call) -> None:
        """
        Add a call to the supervisor. Used by `send_call`.
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
            f"<{self.__class__.__name__} call={self._call},"
            f" submit_fn={self._submit_fn.__name__!r},"
            f" owner={self._owner_thread.name!r}>"
        )


class SyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        call: Call[T],
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(call=call, submit_fn=submit_fn, timeout=timeout)
        self._queue: queue.Queue = queue.Queue()
        self.is_async = False

    def put_call(self, callback: Call):
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


class AsyncSupervisor(Supervisor[T]):
    def __init__(
        self,
        call: Call[T],
        submit_fn: Callable[..., concurrent.futures.Future],
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(call=call, submit_fn=submit_fn, timeout=timeout)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self.is_async = True

    def put_call(self, callback: Call):
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
