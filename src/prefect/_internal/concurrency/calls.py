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
    CancelContext,
    cancel_async_at,
    cancel_sync_at,
)
from prefect.logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")


logger = get_logger("prefect._internal.concurrency.calls")


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
    cancel_context: CancelContext = dataclasses.field(
        default_factory=lambda: CancelContext(timeout=None)
    )
    runner: Optional["Portal"] = None
    waiter: Optional["Portal"] = None

    @classmethod
    def new(cls, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> "Call[T]":
        return cls(
            future=concurrent.futures.Future(),
            fn=__fn,
            args=args,
            kwargs=kwargs,
            context=contextvars.copy_context(),
        )

    def set_timeout(self, timeout: Optional[float] = None) -> None:
        """
        Set the timeout for the call.

        WARNING: The timeout begins immediately, not when the call starts.
        """
        if self.future.done() or self.future.running():
            raise RuntimeError("Timeouts cannot be added when the call has started.")

        self.cancel_context = CancelContext(timeout=timeout)
        logger.debug("Set cancel context %r for call %r", self.cancel_context, self)

    def set_runner(self, portal: "Portal") -> None:
        """
        Update the portal used to run this call.
        """
        if self.runner is not None:
            raise RuntimeError("The portal is already set for this call.")

        self.runner = portal

    def set_waiter(self, portal: "Portal") -> None:
        """
        Set a portal to run callbacks while waiting for this call.
        """
        if self.waiter is not None:
            raise RuntimeError("A waiter has already been set for this call.")

        self.waiter = portal

    def add_waiting_callback(self, call: "Call") -> None:
        """
        Send a callback to the waiter.
        """
        if self.waiter is None:
            raise RuntimeError("No waiter has been configured.")

        if self.future.done():
            raise RuntimeError("The call is already done.")

        self.waiter.submit(call)

    def run(self) -> Optional[Awaitable[T]]:
        """
        Execute the call and place the result on the future.

        All exceptions during execution of the call are captured.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel():
            logger.debug("Skipping execution of cancelled call %r", self)
            return None

        logger.debug(
            "Running call %r in thread %r with cancel context %r",
            self,
            threading.current_thread().name,
            self.cancel_context,
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
        return await asyncio.wrap_future(self.future)

    def cancelled(self) -> bool:
        """
        Check if the call was cancelled.
        """
        return self.cancel_context.cancelled() or self.future.cancelled()

    def _run_sync(self):
        try:
            with set_current_call(self):
                with cancel_sync_at(self.cancel_context.deadline) as ctx:
                    ctx.chain(self.cancel_context, bidirectional=True)
                    result = self.fn(*self.args, **self.kwargs)

            # Return the coroutine for async execution
            if inspect.isawaitable(result):
                return result

        except BaseException as exc:
            self.cancel_context.mark_completed()
            self.future.set_exception(exc)
            logger.debug("Encountered exception in call %r", self)
            # Prevent reference cycle in `exc`
            del self
        else:
            self.cancel_context.mark_completed()  # noqa: F821
            self.future.set_result(result)  # noqa: F821
            logger.debug("Finished call %r", self)  # noqa: F821

    async def _run_async(self, coro):
        try:
            with set_current_call(self):
                with self.cancel_context:
                    with cancel_async_at(self.cancel_context.deadline) as ctx:
                        logger.debug("%r using async cancel scope %r", self, ctx)
                        ctx.chain(self.cancel_context, bidirectional=True)
                        result = await coro
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
