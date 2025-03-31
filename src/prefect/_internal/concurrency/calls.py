"""
Implementation of the `Call` data structure for transport of deferred function calls
and low-level management of call execution.
"""

import abc
import asyncio
import concurrent.futures
import contextlib
import contextvars
import dataclasses
import inspect
import threading
import weakref
from collections.abc import Awaitable, Generator
from concurrent.futures._base import (
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
    FINISHED,
    RUNNING,
)
from typing import TYPE_CHECKING, Any, Callable, Generic, Optional, Union

from typing_extensions import ParamSpec, Self, TypeAlias, TypeVar, TypeVarTuple

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.cancellation import (
    AsyncCancelScope,
    CancelledError,
    cancel_async_at,
    cancel_sync_at,
    get_deadline,
)
from prefect._internal.concurrency.event_loop import get_running_loop

T = TypeVar("T", infer_variance=True)
Ts = TypeVarTuple("Ts")
P = ParamSpec("P")

_SyncOrAsyncCallable: TypeAlias = Callable[P, Union[T, Awaitable[T]]]


# Tracks the current call being executed. Note that storing the `Call`
# object for an async call directly in the contextvar appears to create a
# memory leak, despite the fact that we `reset` when leaving the context
# that sets this contextvar. A weakref avoids the leak and works because a)
# we already have strong references to the `Call` objects in other places
# and b) this is used for performance optimizations where we have fallback
# behavior if this weakref is garbage collected. A fix for issue #10952.
current_call: contextvars.ContextVar["weakref.ref[Call[Any]]"] = (  # novm
    contextvars.ContextVar("current_call")
)

# Create a strong reference to tasks to prevent destruction during execution errors
_ASYNC_TASK_REFS: set[asyncio.Task[None]] = set()


@contextlib.contextmanager
def set_current_call(call: "Call[Any]") -> Generator[None, Any, None]:
    token = current_call.set(weakref.ref(call))
    try:
        yield
    finally:
        current_call.reset(token)


class Future(concurrent.futures.Future[T]):
    """
    Extension of `concurrent.futures.Future` with support for cancellation of running
    futures.

    Used by `Call`.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
        self._cancel_scope = None
        self._deadline = None
        self._cancel_callbacks: list[Callable[[], None]] = []
        self._name = name
        self._timed_out = False

    def set_running_or_notify_cancel(self, timeout: Optional[float] = None):
        self._deadline = get_deadline(timeout)
        return super().set_running_or_notify_cancel()

    @contextlib.contextmanager
    def enforce_async_deadline(self) -> Generator[AsyncCancelScope]:
        with cancel_async_at(self._deadline, name=self._name) as self._cancel_scope:
            for callback in self._cancel_callbacks:
                self._cancel_scope.add_cancel_callback(callback)
            yield self._cancel_scope

    @contextlib.contextmanager
    def enforce_sync_deadline(self):
        with cancel_sync_at(self._deadline, name=self._name) as self._cancel_scope:
            for callback in self._cancel_callbacks:
                self._cancel_scope.add_cancel_callback(callback)
            yield self._cancel_scope

    def add_cancel_callback(self, callback: Callable[[], Any]) -> None:
        """
        Add a callback to be enforced on cancellation.

        Unlike "done" callbacks, this callback will be invoked _before_ the future is
        cancelled. If added after the future is cancelled, nothing will happen.
        """
        # If we were to invoke cancel callbacks the same as "done" callbacks, we
        # would not propagate chained cancellation in waiters in time to actually
        # interrupt calls.
        if self._cancel_scope:
            # Add callback to current cancel scope if it exists
            self._cancel_scope.add_cancel_callback(callback)

        # Also add callbacks to tracking list
        self._cancel_callbacks.append(callback)

    def timedout(self) -> bool:
        with self._condition:
            return self._timed_out

    def cancel(self) -> bool:
        """Cancel the future if possible.

        Returns True if the future was cancelled, False otherwise. A future cannot be
        cancelled if it has already completed.
        """
        with self._condition:
            # Unlike the stdlib, we allow attempted cancellation of RUNNING futures
            if self._state in [RUNNING]:
                if self._cancel_scope is None:
                    return False
                elif not self._cancel_scope.cancelled():
                    # Perform cancellation
                    if not self._cancel_scope.cancel():
                        return False

            if self._state in [FINISHED]:
                return False

            if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
                return True

            # Normally cancel callbacks are handled by the cancel scope but if there
            # is not one let's respect them still
            if not self._cancel_scope:
                for callback in self._cancel_callbacks:
                    callback()

            self._state = CANCELLED
            self._condition.notify_all()

        self._invoke_callbacks()
        return True

    if TYPE_CHECKING:

        def __get_result(self) -> T: ...

    def result(self, timeout: Optional[float] = None) -> T:
        """Return the result of the call that the future represents.

        Args:
            timeout: The number of seconds to wait for the result if the future
                isn't done. If None, then there is no limit on the wait time.

        Returns:
            The result of the call that the future represents.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the given
                timeout.
            Exception: If the call raised then that exception will be raised.
        """
        try:
            with self._condition:
                if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
                    # Raise Prefect cancelled error instead of
                    # `concurrent.futures._base.CancelledError`
                    raise CancelledError()
                elif self._state == FINISHED:
                    return self.__get_result()

                self._condition.wait(timeout)

                if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
                    # Raise Prefect cancelled error instead of
                    # `concurrent.futures._base.CancelledError`
                    raise CancelledError()
                elif self._state == FINISHED:
                    return self.__get_result()
                else:
                    raise TimeoutError()
        finally:
            # Break a reference cycle with the exception in self._exception
            self = None

    _done_callbacks: list[Callable[[Self], object]]

    def _invoke_callbacks(self) -> None:
        """
        Invoke our done callbacks and clean up cancel scopes and cancel
        callbacks. Fixes a memory leak that hung on to Call objects,
        preventing garbage collection of Futures.

        A fix for #10952.
        """
        if self._done_callbacks:
            done_callbacks = self._done_callbacks[:]
            self._done_callbacks[:] = []

            for callback in done_callbacks:
                try:
                    callback(self)
                except Exception:
                    logger.exception("exception calling callback for %r", self)

        self._cancel_callbacks = []
        if self._cancel_scope:
            setattr(self._cancel_scope, "_callbacks", [])
            self._cancel_scope = None


@dataclasses.dataclass
class Call(Generic[T]):
    """
    A deferred function call.
    """

    future: Future[T]
    fn: "_SyncOrAsyncCallable[..., T]"
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    context: contextvars.Context
    timeout: Optional[float]
    runner: Optional["Portal"] = None

    @classmethod
    def new(
        cls,
        __fn: _SyncOrAsyncCallable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Self:
        return cls(
            future=Future(name=getattr(__fn, "__name__", str(__fn))),
            fn=__fn,
            args=args,
            kwargs=kwargs,
            context=contextvars.copy_context(),
            timeout=None,
        )

    def set_timeout(self, timeout: Optional[float] = None) -> None:
        """
        Set the timeout for the call.

        The timeout begins when the call starts.
        """
        if self.future.done() or self.future.running():
            raise RuntimeError("Timeouts cannot be added when the call has started.")

        self.timeout = timeout

    def set_runner(self, portal: "Portal") -> None:
        """
        Update the portal used to run this call.
        """
        if self.runner is not None:
            raise RuntimeError("The portal is already set for this call.")

        self.runner = portal

    def run(self) -> Optional[Awaitable[None]]:
        """
        Execute the call and place the result on the future.

        All exceptions during execution of the call are captured.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel(self.timeout):
            logger.debug("Skipping execution of cancelled call %r", self)
            return None

        logger.debug(
            "Running call %r in thread %r%s",
            self,
            threading.current_thread().name,
            f" with timeout of {self.timeout}s" if self.timeout is not None else "",
        )

        coro = self.context.run(self._run_sync)

        if coro is not None:
            loop = get_running_loop()
            if loop:
                # If an event loop is available, return a task to be awaited
                # Note we must create a task for context variables to propagate
                logger.debug(
                    "Scheduling coroutine for call %r in running loop %r",
                    self,
                    loop,
                )
                task = self.context.run(loop.create_task, self._run_async(coro))

                # Prevent tasks from being garbage collected before completion
                # See https://docs.python.org/3.10/library/asyncio-task.html#asyncio.create_task
                _ASYNC_TASK_REFS.add(task)
                asyncio.ensure_future(task).add_done_callback(
                    lambda _: _ASYNC_TASK_REFS.remove(task)
                )

                return task

            else:
                # Otherwise, execute the function here
                logger.debug("Executing coroutine for call %r in new loop", self)
                return self.context.run(asyncio.run, self._run_async(coro))

        return None

    def result(self, timeout: Optional[float] = None) -> T:
        """
        Wait for the result of the call.

        Not safe for use from asynchronous contexts.
        """
        return self.future.result(timeout=timeout)

    async def aresult(self):
        """
        Wait for the result of the call.

        For use from asynchronous contexts.
        """
        try:
            return await asyncio.wrap_future(self.future)
        except asyncio.CancelledError as exc:
            raise CancelledError() from exc

    def cancelled(self) -> bool:
        """
        Check if the call was cancelled.
        """
        return self.future.cancelled()

    def timedout(self) -> bool:
        """
        Check if the call timed out.
        """
        return self.future.timedout()

    def cancel(self) -> bool:
        return self.future.cancel()

    def _run_sync(self) -> Optional[Awaitable[T]]:
        cancel_scope = None
        try:
            with set_current_call(self):
                with self.future.enforce_sync_deadline() as cancel_scope:
                    try:
                        result = self.fn(*self.args, **self.kwargs)
                    finally:
                        # Forget this call's arguments in order to free up any memory
                        # that may be referenced by them; after a call has happened,
                        # there's no need to keep a reference to them
                        with contextlib.suppress(AttributeError):
                            del self.args, self.kwargs

            # Return the coroutine for async execution
            if inspect.isawaitable(result):
                return result

        except CancelledError:
            # Report cancellation
            # in rare cases, enforce_sync_deadline raises CancelledError
            # prior to yielding
            if cancel_scope is None:
                self.future.cancel()
                return None
            if cancel_scope.timedout():
                setattr(self.future, "_timed_out", True)
                self.future.cancel()
            elif cancel_scope.cancelled():
                self.future.cancel()
            else:
                raise
        except BaseException as exc:
            logger.debug("Encountered exception in call %r", self, exc_info=True)
            self.future.set_exception(exc)

            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)  # noqa: F821
            logger.debug("Finished call %r", self)  # noqa: F821

    async def _run_async(self, coro: Awaitable[T]) -> None:
        cancel_scope = result = None
        try:
            with set_current_call(self):
                with self.future.enforce_async_deadline() as cancel_scope:
                    try:
                        result = await coro
                    finally:
                        # Forget this call's arguments in order to free up any memory
                        # that may be referenced by them; after a call has happened,
                        # there's no need to keep a reference to them
                        with contextlib.suppress(AttributeError):
                            del self.args, self.kwargs
        except CancelledError:
            # Report cancellation
            if TYPE_CHECKING:
                assert cancel_scope is not None
            if cancel_scope.timedout():
                setattr(self.future, "_timed_out", True)
                self.future.cancel()
            elif cancel_scope.cancelled():
                self.future.cancel()
            else:
                raise
        except BaseException as exc:
            logger.debug("Encountered exception in async call %r", self, exc_info=True)

            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            del self
        else:
            # F821 ignored because Ruff gets confused about the del self above.
            self.future.set_result(result)  # noqa: F821
            logger.debug("Finished async call %r", self)  # noqa: F821

    def __call__(self) -> Union[T, Awaitable[T]]:
        """
        Execute the call and return its result.

        All executions during execution of the call are re-raised.
        """
        coro = self.run()

        # Return an awaitable if in an async context
        if coro is not None:

            async def run_and_return_result() -> T:
                await coro
                return self.result()

            return run_and_return_result()
        else:
            return self.result()

    def __repr__(self) -> str:
        name = getattr(self.fn, "__name__", str(self.fn))

        try:
            args, kwargs = self.args, self.kwargs
        except AttributeError:
            call_args = "<dropped>"
        else:
            call_args = ", ".join(
                [repr(arg) for arg in args]
                + [f"{key}={repr(val)}" for key, val in kwargs.items()]
            )

        # Enforce a maximum length
        if len(call_args) > 100:
            call_args = call_args[:100] + "..."

        return f"{name}({call_args})"


class Portal(abc.ABC):
    """
    Allows submission of calls to execute elsewhere.
    """

    @abc.abstractmethod
    def submit(self, call: "Call[T]") -> "Call[T]":
        """
        Submit a call to execute elsewhere.

        The call's result can be retrieved with `call.result()`.

        Returns the call for convenience.
        """
