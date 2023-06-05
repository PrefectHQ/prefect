"""
Utilities for enforcement of timeouts in synchronous and asynchronous contexts.
"""

import asyncio
import contextlib
import ctypes
import os
import signal
import sys
import threading
import time
from typing import Callable, List, Optional, Type


from prefect._internal.concurrency.event_loop import get_running_loop
from prefect.logging import get_logger

# TODO: We should update the format for this logger to include the current thread
logger = get_logger("prefect._internal.concurrency.timeouts")


class CancelledError(asyncio.CancelledError):
    pass


class TimeoutError(CancelledError):
    pass


class CancelContext:
    """
    Tracks if a cancel context manager was cancelled.

    A context cannot be marked as cancelled after it is reported as completed.
    """

    def __init__(
        self,
        timeout: Optional[float],
        cancel: Optional[Callable[[], None]] = None,
        name: Optional[str] = None,
    ) -> None:
        self._timeout = timeout
        self._deadline = get_deadline(timeout)
        self._cancelled: bool = False
        self._chained: List["CancelContext"] = []
        self._lock = threading.Lock()
        self._completed = False
        self._cancel = cancel
        self._name = name

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def timeout(self) -> Optional[float]:
        return self._timeout

    @property
    def deadline(self) -> Optional[float]:
        return self._deadline

    def cancel(self):
        if self._mark_cancelled():
            if self._cancel is not None:
                logger.debug("Cancelling %r with %r", self, self._cancel)
                self._cancel()

            for ctx in self._chained:
                logger.debug("%r cancelling chained context %r", self, ctx)
                try:
                    ctx.cancel()
                except Exception:
                    logger.warning(
                        "%r encountered exception cancelling chained context %r",
                        self,
                        ctx,
                        exc_info=True,
                    )

            return True

        else:
            logger.debug("%r is already finished", self)
            return False

    def cancelled(self):
        with self._lock:
            return self._cancelled

    def completed(self):
        with self._lock:
            return self._completed

    def _mark_cancelled(self) -> bool:
        with self._lock:
            if self._completed:
                return False  # Do not mark completed tasks as cancelled

            if self._cancelled:
                return False  # Already marked as cancelled

            logger.debug("Marked %r as cancelled", self)
            self._cancelled = True

        return True

    def mark_completed(self) -> bool:
        with self._lock:
            if self._cancelled:
                return False  # Do not mark cancelled tasks as completed

            if self._completed:
                logger.debug("%r already completed", self)
                return False  # Already marked as completed

            logger.debug("Marked %r as completed", self)
            self._completed = True
            return True

    def chain(self, ctx: "CancelContext", bidirectional: bool = False) -> None:
        """
        When this context is cancelled, cancel the given context as well.

        If this context is already cancelled, the given context will be cancelled
        immediately.
        """
        with self._lock:
            if self._cancelled:
                ctx.cancel()
            else:
                self._chained.append(ctx)

        if bidirectional:
            ctx.chain(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.mark_completed()

    def __repr__(self) -> str:
        timeout = f" timeout={self._timeout:.2f}" if self._timeout else ""
        name = f"for {self._name!r}" if self._name else ""
        return f"<CancelContext {name} at {hex(id(self))} {timeout}>"


def get_deadline(timeout: Optional[float]):
    """
    Compute an deadline given a timeout.

    Uses a monotonic clock.
    """
    if timeout is None:
        return None

    return time.monotonic() + timeout


def get_timeout(deadline: Optional[float]):
    """
    Compute an timeout given a deadline.

    Uses a monotonic clock.
    """
    if deadline is None:
        return None

    return max(0, deadline - time.monotonic())


@contextlib.contextmanager
def cancel_async_at(deadline: Optional[float], name: Optional[str] = None):
    """
    Cancel any async calls within the context if it does not exit by the given deadline.

    Deadlines must be computed with the monotonic clock. See `get_deadline`.

    A timeout error will be raised on the next `await` when the timeout expires.

    Yields a `CancelContext`.
    """
    current_task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    _handle = None

    def cancel():
        if loop is get_running_loop():
            current_task.cancel()
        else:
            # `Task.cancel`` is not thread safe
            loop.call_soon_threadsafe(current_task.cancel)

    try:
        with CancelContext(
            timeout=get_timeout(deadline), cancel=cancel, name=name
        ) as ctx:
            if deadline is not None:
                _handle = loop.call_at(deadline, ctx.cancel)
            yield ctx

            # Throw the cancelled error if it did not raise
            if ctx.cancelled():
                raise asyncio.CancelledError()

    except asyncio.CancelledError as exc:
        raise (
            TimeoutError()
            if deadline is not None and time.monotonic() >= deadline
            else CancelledError()
        ) from exc
    else:
        if _handle:
            # It is not necessary to cancel the deadline handle, but it's nice to clean
            # it up early if we can
            _handle.cancel()


@contextlib.contextmanager
def cancel_async_after(timeout: Optional[float], name: Optional[str] = None):
    """
    Cancel any async calls within the context if it does not exit after the given
    timeout.

    A timeout error will be raised on the next `await` when the timeout expires.

    Yields a `CancelContext`.
    """
    deadline = (time.monotonic() + timeout) if timeout is not None else None
    with cancel_async_at(deadline, name=name) as ctx:
        yield ctx


@contextlib.contextmanager
def cancel_sync_at(deadline: Optional[float], name: Optional[str] = None):
    """
    Cancel any sync calls within the context if it does not exit by the given deadline.

    Deadlines must be computed with the monotonic clock. See `get_deadline`.

    The cancel method varies depending on if this is called in the main thread or not.
    See `cancel_sync_after` for details

    Yields a `CancelContext`.
    """
    timeout = max(0, deadline - time.monotonic()) if deadline is not None else None

    with cancel_sync_after(timeout, name=name) as ctx:
        yield ctx


@contextlib.contextmanager
def cancel_sync_after(timeout: Optional[float], name: Optional[str] = None):
    """
    Cancel any sync calls within the context if it does not exit after the given
    timeout.

    The timeout method varies depending on if this is called in the main thread or not.
    See `_alarm_based_timeout` and `_watcher_thread_based_timeout` for details.

    Yields a `CancelContext`.
    """
    if sys.platform.startswith("win"):
        # Timeouts cannot be enforced on Windows
        if timeout is not None:
            logger.warning(
                "Entered cancel context on Windows; %.2f timeout will not be enforced.",
                timeout,
            )
        yield CancelContext(timeout=None, cancel=lambda: None, name=name)
        return

    existing_alarm_handler = signal.getsignal(signal.SIGALRM) != signal.SIG_DFL

    if (
        threading.current_thread() is threading.main_thread()
        # Avoid nested alarm handlers; it's hard to follow and they will interfere with
        # each other
        and not existing_alarm_handler
        # Avoid using an alarm when there is no timeout; it's better saved for that case
        and timeout is not None
    ):
        method = _alarm_based_timeout
        method_name = "alarm"
    else:
        method = _watcher_thread_based_timeout
        method_name = "watcher"

    with method(timeout, name=name) as ctx:
        logger.debug(
            "Entered synchronous %s based cancel context %r",
            method_name,
            ctx,
        )
        yield ctx


@contextlib.contextmanager
def _alarm_based_timeout(timeout: Optional[float], name: Optional[str] = None):
    """
    Enforce a timeout using an alarm.

    Sets an alarm for `timeout` seconds, then raises a timeout error if the context is
    not exited before the deadline.

    !!! Alarms cannot be floats, so the timeout is rounded up to the nearest integer.

    Alarms have the benefit of interrupt sys calls like `sleep`, but signals are always
    raised in the main thread and this cannot be used elsewhere.
    """
    current_thread = threading.current_thread()
    if current_thread is not threading.main_thread():
        raise ValueError("Alarm based timeouts can only be used in the main thread.")

    # Create a context that raises an alarm signal on cancellation
    ctx = CancelContext(
        timeout=timeout,
        cancel=lambda: os.kill(os.getpid(), signal.SIGALRM),
        name=name,
    )

    previous_alarm_handler = signal.getsignal(signal.SIGALRM)

    def sigalarm_to_error(*args):
        logger.debug("Cancel fired for alarm based cancel context %r", ctx)

        # Ensure the context is marked as cancelled
        ctx._cancel = None
        ctx.cancel()

        # Cancel this context
        raise (
            TimeoutError()
            if timeout is not None and time.monotonic() >= ctx._deadline
            else CancelledError()
        )

    if previous_alarm_handler != signal.SIG_DFL:
        logger.warning(f"Overriding existing alarm handler {previous_alarm_handler}")

    # Capture alarm signals and raise a timeout
    signal.signal(signal.SIGALRM, sigalarm_to_error)

    # Set a timer to raise an alarm signal
    if timeout is not None:
        # Use `setitimer` instead of `signal.alarm` for float support; raises a SIGALRM
        previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout)

    try:
        yield ctx
    finally:
        if timeout is not None:
            # Restore the previous timer
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)

        ctx.mark_completed()

        # Restore the previous signal handler
        signal.signal(signal.SIGALRM, previous_alarm_handler)


@contextlib.contextmanager
def _watcher_thread_based_timeout(timeout: Optional[float], name: Optional[str] = None):
    """
    Enforce a timeout using a watcher thread.

    Creates a thread that sleeps for `timeout` seconds, then sends a timeout error to
    the supervised (current) thread if the context is not exited before the deadline.

    Note this will not interrupt sys calls like `sleep`.
    """
    event = threading.Event()
    enforcer = None
    supervised_thread = threading.current_thread()

    def _send_exception(exc):
        if supervised_thread.is_alive():
            logger.debug("Sending exception to supervised thread %r", supervised_thread)
            try:
                _send_exception_to_thread(supervised_thread, exc)
            except ValueError:
                # If the thread is gone; just move on without error
                trace("Thread missing!")
            else:
                logger.debug("Sent exception")

        # Wait for the supervised thread to exit its context
        trace("Waiting for supervised thread to exit...")
        event.wait()

    def cancel():
        return _send_exception(CancelledError)

    ctx = CancelContext(timeout=timeout, cancel=cancel, name=name)

    def timeout_enforcer():
        if not event.wait(timeout):
            logger.debug(
                "Cancel fired for watcher based timeout for thread %r and context %r",
                supervised_thread.name,
                ctx,
            )
            if ctx.mark_cancelled():
                _send_exception(TimeoutError)

    if timeout is not None:
        enforcer = threading.Thread(
            target=timeout_enforcer,
            name=f"timeout-watcher {name or '<unnamed>'} {timeout:.2f}",
        )
        enforcer.start()

    try:
        yield ctx
    finally:
        event.set()
        ctx.mark_completed()
        if enforcer:
            enforcer.join()


def _send_exception_to_thread(thread: threading.Thread, exc_type: Type[BaseException]):
    """
    Raise an exception in a thread.

    This will not interrupt long-running system calls like `sleep` or `wait`.
    """
    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), ctypes.py_object(exc_type)
    )
    if ret == 0:
        raise ValueError("Thread not found.")
