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
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, Tuple, TypeVar

from typing_extensions import ParamSpec

from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.timeouts import (
    CancelledError,
    TimeoutError,
    cancel_async_at,
    get_deadline,
    cancel_sync_at,
)
from concurrent.futures._base import (
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
    FINISHED,
    RUNNING,
)

from prefect._internal.concurrency.inspection import trace

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
    def __init__(self) -> None:
        super().__init__()
        self._cancel_scope = None
        self.deadline = None
        self._timed_out = False

    def set_running_or_notify_cancel(self, timeout: Optional[float] = None):
        self.deadline = get_deadline(timeout)
        return super().set_running_or_notify_cancel()

    @contextlib.contextmanager
    def enforce_async_deadline(self):
        try:
            with cancel_async_at(self.deadline) as self._cancel_scope:
                yield
        except (CancelledError, TimeoutError) as exc:
            # Report cancellation
            if self._cancel_scope.cancelled():
                self._timed_out = isinstance(exc, TimeoutError)
                self.cancel()
            raise

    @contextlib.contextmanager
    def enforce_sync_deadline(self):
        try:
            with cancel_sync_at(self.deadline) as self._cancel_scope:
                yield
        except (CancelledError, TimeoutError) as exc:
            # Report cancellation
            if self._cancel_scope.cancelled():
                self._timed_out = isinstance(exc, TimeoutError)
                self.cancel()
            raise

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
                    # Perfom cancellation
                    if not self._cancel_scope.cancel():
                        return False

            if self._state in [FINISHED]:
                return False

            if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
                return True

            self._state = CANCELLED
            self._condition.notify_all()

        self._invoke_callbacks()
        return True

    def timed_out(self) -> bool:
        with self._condition:
            return self._timed_out


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
            future=Future(),
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
            trace("Skipping execution of cancelled call %r", self)
            return None

        trace(
            "Running call %r in thread %r with timeout %s",
            self,
            threading.current_thread().name,
            self.timeout,
        )

        coro = self.context.run(self._run_sync)

        if coro is not None:
            loop = get_running_loop()
            if loop:
                # If an event loop is available, return a task to be awaited
                # Note we must create a task for context variables to propagate
                trace("Scheduling coroutine for call %r in running loop %r", self, loop)
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
                trace("Executing coroutine for call %r in new loop", self)
                return self.context.run(asyncio.run, self._run_async(coro))

        return None

    def result(self, timeout: Optional[float] = None) -> T:
        """
        Wait for the result of the call.

        Not safe for use from asynchronous contexts.
        """
        try:
            return self.future.result(timeout=timeout)
        except concurrent.futures._base.CancelledError as exc:
            if self.cancelled():
                if self.future.timed_out():
                    raise TimeoutError() from exc
                raise CancelledError() from exc
            raise

    async def aresult(self):
        """
        Wait for the result of the call.

        For use from asynchronous contexts.
        """
        try:
            return await asyncio.wrap_future(self.future)
        except asyncio.CancelledError as exc:
            if self.cancelled():
                if self.future.timed_out():
                    raise TimeoutError() from exc
                raise CancelledError() from exc
            raise

    def cancelled(self) -> bool:
        """
        Check if the call was cancelled.
        """
        return self.future.cancelled()

    def cancel(self) -> bool:
        return self.future.cancel()

    def _run_sync(self):
        try:
            with set_current_call(self):
                with self.future.enforce_sync_deadline():
                    result = self.fn(*self.args, **self.kwargs)

            # Return the coroutine for async execution
            if inspect.isawaitable(result):
                return result

        except BaseException as exc:
            trace("Encountered exception in call %r", self, exc_info=True)
            if not self.future.cancelled():
                self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)  # noqa: F821
            trace("Finished call %r", self)  # noqa: F821

    async def _run_async(self, coro):
        try:
            with set_current_call(self):
                with self.future.enforce_async_deadline():
                    result = await coro
        except BaseException as exc:
            trace("Encountered exception in async call %r", self, exc_info=True)
            if not self.future.cancelled():
                self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.future.set_result(result)  # noqa: F821
            trace("Finished async call %r", self)  # noqa: F821

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
