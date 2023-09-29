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
from concurrent.futures._base import (
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
    FINISHED,
    RUNNING,
)
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, Tuple, TypeVar

from typing_extensions import ParamSpec

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.cancellation import (
    CancelledError,
    cancel_async_at,
    cancel_sync_at,
    get_deadline,
)
from prefect._internal.concurrency.event_loop import get_running_loop

T = TypeVar("T")
P = ParamSpec("P")


# Tracks the current call being executed
current_call: contextvars.ContextVar["Call"] = contextvars.ContextVar("current_call")

# Create a strong reference to tasks to prevent destruction during execution errors
_ASYNC_TASK_REFS = set()


def get_current_call() -> Optional["Call"]:
    return current_call.get(None)


@contextlib.contextmanager
def set_current_call(call: "Call"):
    token = current_call.set(call)
    try:
        yield
    finally:
        current_call.reset(token)


class Future(concurrent.futures.Future):
    """
    Extension of `concurrent.futures.Future` with support for cancellation of running
    futures.

    Used by `Call`.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
        self._cancel_scope = None
        self._deadline = None
        self._cancel_callbacks = []
        self._name = name
        self._timed_out = False

    def set_running_or_notify_cancel(self, timeout: Optional[float] = None):
        self._deadline = get_deadline(timeout)
        return super().set_running_or_notify_cancel()

    @contextlib.contextmanager
    def enforce_async_deadline(self):
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

    def add_cancel_callback(self, callback: Callable[[], None]):
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

    def cancel(self):
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

    def result(self, timeout=None):
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


@dataclasses.dataclass
class Call(Generic[T]):
    """
    A deferred function call.
    """

    future: Future
    fn: Callable[..., T]
    args: Tuple
    kwargs: Dict[str, Any]
    context: contextvars.Context
    timeout: float
    runner: Optional["Portal"] = None

    @classmethod
    def new(cls, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> "Call[T]":
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

    def run(self) -> Optional[Awaitable[T]]:
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
                    "Scheduling coroutine for call %r in running loop %r", self, loop
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

    def _run_sync(self):
        cancel_scope = None
        try:
            with set_current_call(self):
                with self.future.enforce_sync_deadline() as cancel_scope:
                    result = self.fn(*self.args, **self.kwargs)

            # Return the coroutine for async execution
            if inspect.isawaitable(result):
                return result

        except CancelledError:
            # Report cancellation
            if cancel_scope.timedout():
                self.future._timed_out = True
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

    async def _run_async(self, coro):
        cancel_scope = None
        try:
            with set_current_call(self):
                with self.future.enforce_async_deadline() as cancel_scope:
                    result = await coro
        except CancelledError:
            # Report cancellation
            if cancel_scope.timedout():
                self.future._timed_out = True
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
            self.future.set_result(result)  # noqa: F821
            logger.debug("Finished async call %r", self)  # noqa: F821

    def __call__(self) -> T:
        """
        Execute the call and return its result.

        All executions during execution of the call are re-raised.
        """
        coro = self.run()

        # Return an awaitable if in an async context
        if coro is not None:

            async def run_and_return_result():
                await coro
                return self.result()

            return run_and_return_result()
        else:
            return self.result()

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


class Portal(abc.ABC):
    """
    Allows submission of calls to execute elsewhere.
    """

    @abc.abstractmethod
    def submit(self, call: "Call") -> "Call":
        """
        Submit a call to execute elsewhere.

        The call's result can be retrieved with `call.result()`.

        Returns the call for convenience.
        """
