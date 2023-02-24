import contextlib
import ctypes
import math
import signal
import sys
import threading
import time
from typing import Type

import anyio


class CancelContext:
    """
    Tracks if a cancel context manager was cancelled.

    The `cancelled` property is threadsafe.
    """

    def __init__(self) -> None:
        self._cancelled: bool = False
        self._lock = threading.Lock()

    @property
    def cancelled(self):
        with self._lock:
            return self._cancelled

    @cancelled.setter
    def cancelled(self, value: bool):
        with self._lock:
            self._cancelled = value


@contextlib.contextmanager
def cancel_async_after(timeout: float):
    """
    Cancel any async calls within the context if it does not exit after the given
    timeout.

    A timeout error will be raised on the next `await` when the timeout expires.

    Yields a `CancelContext`.
    """
    ctx = CancelContext()
    try:
        with anyio.fail_after(timeout) as cancel_scope:
            yield ctx
    finally:
        ctx.cancelled = cancel_scope.cancel_called


@contextlib.contextmanager
def cancel_sync_after(timeout: float):
    """
    Cancel any sync calls within the context if it does not exit after the given
    timeout.

    The timeout method varies depending on if this is called in the main thread or not.
    See `_alarm_based_timeout` and `_watcher_thread_based_timeout` for details.

    Yields a `CancelContext`.
    """
    ctx = CancelContext()

    if sys.platform.startswith("win"):
        # Timeouts cannot be enforced on Windows
        yield ctx
        return

    if threading.current_thread() is threading.main_thread():
        method = _alarm_based_timeout
    else:
        method = _watcher_thread_based_timeout

    try:
        with method(timeout) as inner_ctx:
            yield ctx
    finally:
        ctx.cancelled = inner_ctx.cancelled


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
    if not threading.current_thread() is threading.main_thread():
        raise ValueError("Alarm based timeouts can only be used in the main thread.")

    ctx = CancelContext()

    def raise_alarm_as_timeout(signum, frame):
        ctx.cancelled = True
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
    ctx = CancelContext()

    def timeout_enforcer():
        time.sleep(timeout)
        if not event.is_set():
            ctx.cancelled = True
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
