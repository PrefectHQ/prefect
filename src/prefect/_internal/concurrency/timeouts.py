import contextlib
import ctypes
import math
import signal
import sys
import threading
import time
from typing import Type

import anyio


@contextlib.contextmanager
def cancel_async_after(timeout: float):
    with anyio.fail_after(timeout):
        yield


@contextlib.contextmanager
def cancel_sync_after(timeout: float):
    if sys.platform.startswith("win"):
        # Timeouts cannot be enforced on Windows
        yield
        return

    if threading.current_thread() is threading.main_thread():
        method = _alarm_based_timeout
    else:
        method = _watcher_thread_based_timeout

    with method(timeout):
        yield


@contextlib.contextmanager
def _alarm_based_timeout(timeout: float):
    """
    Enforce a timeout using an alarm.

    Sets an alarm for `timeout` seconds, then raises a timeout error if the context is
    not exited before the deadline.

    Alarms have the benefit of interrupt sys calls like `sleep`, but signals are always
    raised in the main thread and this cannot be used elsewhere.
    """
    if not threading.current_thread() is threading.main_thread():
        raise ValueError("Alarm based timeouts can only be used in the main thread.")

    def raise_alarm_as_timeout(signum, frame):
        raise TimeoutError()

    try:
        signal.signal(signal.SIGALRM, raise_alarm_as_timeout)
        signal.alarm(math.ceil(timeout))  # alarms do not support floats
        yield
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

    def timeout_enforcer():
        time.sleep(timeout)
        if not event.is_set():
            _send_exception_to_thread(supervised_thread, TimeoutError)

    enforcer = threading.Thread(target=timeout_enforcer, daemon=True)
    enforcer.start()

    try:
        yield
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
