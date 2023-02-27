import contextlib
import ctypes
import math
import signal
import sys
import threading
import time
from typing import Optional, Type

import anyio

from prefect.logging import get_logger

# TODO: We should update the format for this logger to include the current thread
logger = get_logger("prefect._internal.concurrency.timeouts")


class CancelContext:
    """
    Tracks if a cancel context manager was cancelled.

    The `cancelled` property is threadsafe.
    """

    def __init__(self, timeout: Optional[float]) -> None:
        self._timeout = timeout
        self._cancelled: bool = False

    @property
    def timeout(self) -> Optional[float]:
        return self._timeout

    @property
    def cancelled(self):
        return self._cancelled

    def mark_cancelled(self):
        self._cancelled = True


@contextlib.contextmanager
def cancel_async_after(timeout: Optional[float]):
    """
    Cancel any async calls within the context if it does not exit after the given
    timeout.

    A timeout error will be raised on the next `await` when the timeout expires.

    Yields a `CancelContext`.
    """
    ctx = CancelContext(timeout=timeout)
    if timeout is None:
        yield ctx
        return

    try:
        with anyio.fail_after(timeout) as cancel_scope:
            logger.debug(
                f"Entered asynchronous cancel context with %.2f timeout", timeout
            )
            yield ctx
    finally:
        if cancel_scope.cancel_called:
            ctx.mark_cancelled()


def get_deadline(timeout: Optional[float]):
    """
    Compute an deadline given a timeout.

    Uses a monotonic clock.
    """
    if timeout is None:
        return None

    return time.monotonic() + timeout


@contextlib.contextmanager
def cancel_async_at(deadline: Optional[float]):
    """
    Cancel any async calls within the context if it does not exit by the given deadline.

    Deadlines must be computed with the monotonic clock. See `get_deadline`.

    A timeout error will be raised on the next `await` when the timeout expires.

    Yields a `CancelContext`.
    """
    if deadline is None:
        yield CancelContext(timeout=None)
        return

    timeout = max(0, deadline - time.monotonic())

    ctx = CancelContext(timeout=timeout)
    try:
        with cancel_async_after(timeout) as inner_ctx:
            yield ctx
    finally:
        if inner_ctx.cancelled:
            ctx.mark_cancelled()


@contextlib.contextmanager
def cancel_sync_at(deadline: Optional[float]):
    """
    Cancel any sync calls within the context if it does not exit by the given deadline.

    Deadlines must be computed with the monotonic clock. See `get_deadline`.

    The cancel method varies depending on if this is called in the main thread or not.
    See `cancel_sync_after` for details

    Yields a `CancelContext`.
    """
    if deadline is None:
        yield CancelContext(timeout=None)
        return

    timeout = max(0, deadline - time.monotonic())

    ctx = CancelContext(timeout=timeout)
    try:
        with cancel_sync_after(timeout) as inner_ctx:
            yield ctx
    finally:
        if inner_ctx.cancelled:
            ctx.mark_cancelled()


@contextlib.contextmanager
def cancel_sync_after(timeout: Optional[float]):
    """
    Cancel any sync calls within the context if it does not exit after the given
    timeout.

    The timeout method varies depending on if this is called in the main thread or not.
    See `_alarm_based_timeout` and `_watcher_thread_based_timeout` for details.

    Yields a `CancelContext`.
    """
    ctx = CancelContext(timeout=timeout)
    if timeout is None:
        yield ctx
        return

    if sys.platform.startswith("win"):
        # Timeouts cannot be enforced on Windows
        logger.warning(
            f"Entered cancel context on Windows; %.2f timeout will not be enforced.",
            timeout,
        )
        yield ctx
        return

    if threading.current_thread() is threading.main_thread():
        method = _alarm_based_timeout
        method_name = "alarm"
    else:
        method = _watcher_thread_based_timeout
        method_name = "watcher"

    try:
        with method(timeout) as inner_ctx:
            logger.debug(
                f"Entered synchronous cancel context with %.2f %s based timeout",
                timeout,
                method_name,
            )
            yield ctx
    finally:
        if inner_ctx.cancelled:
            ctx.mark_cancelled()


@contextlib.contextmanager
def _alarm_based_timeout(timeout: float):
    """
    Enforce a timeout using an alarm.

    Sets an alarm for `timeout` seconds, then raises a timeout error if the context is
    not exited before the deadline.

    !!! Alarms cannot be floats, so the timeout is rounded up to the nearest integer.

    Alarms have the benefit of interrupt sys calls like `sleep`, but signals are always
    raised in the main thread and this cannot be used elsewhere.
    """
    current_thread = threading.current_thread()
    if not current_thread is threading.main_thread():
        raise ValueError("Alarm based timeouts can only be used in the main thread.")

    ctx = CancelContext(timeout=timeout)

    def raise_alarm_as_timeout(signum, frame):
        ctx.mark_cancelled()
        logger.debug(
            "Cancel fired for alarm based timeout of thread %r", current_thread.name
        )
        raise TimeoutError()

    try:
        signal.signal(signal.SIGALRM, raise_alarm_as_timeout)
        signal.alarm(math.ceil(timeout))  # alarms do not support floats
        yield ctx
    finally:
        signal.alarm(0)  # Clear the alarm when the context exits


@contextlib.contextmanager
def _watcher_thread_based_timeout(timeout: float):
    """
    Enforce a timeout using a watcher thread.

    Creates a thread that sleeps for `timeout` seconds, then sends a timeout error to
    the supervised (current) thread if the context is not exited before the deadline.

    Note this will not interrupt sys calls like `sleep`.
    """
    event = threading.Event()
    supervised_thread = threading.current_thread()
    ctx = CancelContext(timeout=timeout)

    def timeout_enforcer():
        time.sleep(timeout)
        if not event.is_set():
            logger.debug(
                "Cancel fired for watcher based timeout of thread %r",
                supervised_thread.name,
            )
            ctx.mark_cancelled()
            _send_exception_to_thread(supervised_thread, TimeoutError)

    enforcer = threading.Thread(target=timeout_enforcer, daemon=True)
    enforcer.start()

    try:
        yield ctx
    finally:
        event.set()


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
