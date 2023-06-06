"""
Utilities for enforcement of timeouts in synchronous and asynchronous contexts.
"""

import asyncio
import contextlib
import ctypes
import os
import abc
import math
import signal
import anyio
import sys
import threading
import time
from typing import Callable, Optional, Type, Dict


from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency import logger

_THREAD_SHIELDS: Dict[threading.Thread, "ThreadShield"] = {}
_THREAD_SHIELDS_LOCK = threading.Lock()


class ThreadShield:
    """
    A wrapper around a reentrant lock for shielding a thread from remote exceptions.
    This can be used in two ways:

    1. As a context manager from _another_ thread to wait until the shield is released
      by a target before sending an exception.

    2. From the current thread, using `set_exception` to throw the exception when the
      shield is released.

    A reentrant lock means that shields can be nested and the exception will only be
    raised when the last context is exited.
    """

    def __init__(self):
        # Uses the Python implementation of the RLock instead of the C implementation
        # because we need to inspect `_count` directly to check if the lock is active
        # which is needed for delayed exception raising during alarms
        self._lock = threading._RLock()
        self._exception = None

    def __enter__(self) -> None:
        self._lock.__enter__()

    def __exit__(self, *exc_info):
        retval = self._lock.__exit__(*exc_info)

        # Raise the exception if this is the last shield to exit
        if not self.active() and self._exception:
            # Clear the exception to prevent it from being raised again
            exc = self._exception
            self._exception = None
            raise exc from None

        return retval

    def set_exception(self, exc: Exception):
        self._exception = exc

    def active(self) -> bool:
        """
        Returns true if the shield is active.
        """
        return self._lock._count > 0


class CancelledError(asyncio.CancelledError):
    # In Python 3.7, `asyncio.CancelledError` is identical to `concurrent.futures.CancelledError`
    # but in 3.8+ it is a separate class that inherits from `BaseException` instead
    # See https://bugs.python.org/issue32528
    # We want our `CancelledError` to be treated as a `BaseException` and defining it
    # here simplifies downstream logic that needs to know "which" cancelled error to
    # handle.
    pass


def _get_thread_shield(thread) -> ThreadShield:
    with _THREAD_SHIELDS_LOCK:
        if thread not in _THREAD_SHIELDS:
            _THREAD_SHIELDS[thread] = ThreadShield()

        # Perform garbage collection for old threads
        for thread_ in tuple(_THREAD_SHIELDS.keys()):
            if not thread_.is_alive():
                _THREAD_SHIELDS.pop(thread_)

        return _THREAD_SHIELDS[thread]


@contextlib.contextmanager
def shield():
    """
    Prevent code from within the scope from being cancelled.

    """
    with (
        anyio.CancelScope(shield=True)
        if get_running_loop()
        else contextlib.nullcontext()
    ):
        with _get_thread_shield(threading.current_thread()):
            yield


class CancelScope(abc.ABC):
    def __init__(
        self, name: Optional[str] = None, timeout: Optional[float] = None
    ) -> None:
        self.name = name
        self._deadline = None
        self._cancelled = False
        self._completed = False
        self._started = False
        self._start_time = None
        self._end_time = None
        self._timeout = timeout
        self._lock = threading.Lock()
        self._callbacks = []
        super().__init__()

    def __enter__(self):
        with self._lock:
            self._deadline = get_deadline(self._timeout)
            self._started = True
            self._start_time = time.monotonic()
        return self

    def __exit__(self, *_):
        with self._lock:
            if not self._cancelled:
                self._completed = True
            self._end_time = time.monotonic()

    @property
    def timeout(self):
        return self._timeout

    def started(self) -> bool:
        with self._lock:
            return self._started

    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def timedout(self) -> bool:
        with self._lock:
            if not self._end_time or not self._deadline:
                return False
            return self._cancelled and self._end_time > self._deadline

    def set_timeout(self, timeout: float):
        with self._lock:
            if self._started:
                raise RuntimeError("Cannot set timeout after scope has started.")
            self._timeout = timeout

    def completed(self):
        with self._lock:
            return self._completed

    def cancel(self) -> bool:
        with self._lock:
            if not self.started:
                raise RuntimeError("Scope has not been entered.")

            if self._completed:
                return False

            if self._cancelled:
                return True

            self._cancelled = True

        for callback in self._callbacks:
            callback()

        return True

    def add_cancel_callback(self, callback: Callable[[], None]):
        self._callbacks.append(callback)

    def __repr__(self) -> str:
        with self._lock:
            state = (
                "completed"
                if self._completed
                else (
                    "cancelled"
                    if self._cancelled
                    else "running" if self._started else "pending"
                )
            ).upper()
            timeout = f", timeout={self._timeout:.2f}" if self._timeout else ""
            runtime = (
                f", runtime={(self._end_time or time.monotonic()) - self._start_time:.2f}"
                if self._start_time
                else ""
            )
            name = f", name={self.name!r}" if self.name else f"at {hex(id(self))}"
        return f"<{type(self).__name__} {name} {state}{timeout}{runtime}>"


class AsyncCancelScope(CancelScope):
    def __init__(
        self, name: Optional[str] = None, timeout: Optional[float] = None
    ) -> None:
        super().__init__(name=name, timeout=timeout)
        self.loop = None

    def __enter__(self):
        self.loop = asyncio.get_running_loop()

        super().__enter__()

        # Use anyio as the cancellation enforcer because it's very complicated and they
        # have done a good job
        self._inner = anyio.CancelScope(
            deadline=self._deadline if self._deadline is not None else math.inf
        ).__enter__()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._inner.cancel_called:
            # Mark as cancelled
            self.cancel(throw=False)

        super().__exit__(exc_type, exc_val, exc_tb)

        if self.cancelled() and exc_type is not CancelledError:
            # Ensure cancellation error is propagated on exit
            raise CancelledError() from exc_val

        return False

    def cancel(self, throw: bool = True):
        if not super().cancel():
            return False

        if throw:
            if self.loop is get_running_loop():
                self._inner.cancel()
            else:
                # `Task.cancel` is not thread safe
                self.loop.call_soon_threadsafe(self._inner.cancel)

        return True


class SyncCancelScope(CancelScope):
    def __enter__(self):
        super().__enter__()

        if sys.platform.startswith("win"):
            # Timeouts cannot be enforced on Windows
            if self._timeout is not None:
                logger.debug(
                    (
                        "Entered cancel scope on Windows; %.2f timeout will not be"
                        " enforced."
                    ),
                    self._timeout,
                )
            self._method = None
            self._throw_cancel = lambda: None
            return self

        self.thread = threading.current_thread()
        existing_alarm_handler = signal.getsignal(signal.SIGALRM) != signal.SIG_DFL

        if (
            self.thread is threading.main_thread()
            # Avoid nested alarm handlers; it's hard to follow and they will interfere with
            # each other
            and not existing_alarm_handler
            # Avoid using an alarm when there is no timeout; it's better saved for that case
            and self._timeout is not None
        ):
            method = _alarm_based_timeout
            method_name = "alarm"
        else:
            method = _watcher_thread_based_timeout
            method_name = "watcher"

        self._method = method(self)
        self._throw_cancel = self._method.__enter__()
        logger.debug(
            "Entered synchronous %s based cancel scope %r",
            method_name,
            self,
        )
        return self

    def __exit__(self, *_):
        retval = super().__exit__(*_)
        if self._method:
            self._method.__exit__(*_)
        return retval

    def cancel(self, throw: bool = True):
        if not super().cancel():
            return False

        if throw:
            self._throw_cancel()

        return True


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
    with AsyncCancelScope(timeout=get_timeout(deadline), name=name) as ctx:
        yield ctx


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
    with SyncCancelScope(timeout=timeout, name=name) as ctx:
        yield ctx


@contextlib.contextmanager
def _alarm_based_timeout(scope: CancelScope):
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

    previous_alarm_handler = signal.getsignal(signal.SIGALRM)

    def cancel():
        with _get_thread_shield(threading.main_thread()):
            os.kill(os.getpid(), signal.SIGALRM)

    def sigalarm_to_error(*args):
        logger.debug("Cancel fired for alarm based cancel scope %r", scope)
        if scope.cancel(throw=False):
            shield = _get_thread_shield(threading.main_thread())
            if shield.active():
                logger.debug("Thread shield active; delaying exception...")
                shield.set_exception(CancelledError())
            else:
                raise CancelledError()

    if previous_alarm_handler != signal.SIG_DFL:
        logger.warning(f"Overriding existing alarm handler {previous_alarm_handler}")

    # Capture alarm signals and raise a timeout
    signal.signal(signal.SIGALRM, sigalarm_to_error)

    # Set a timer to raise an alarm signal
    if scope.timeout is not None:
        # Use `setitimer` instead of `signal.alarm` for float support; raises a SIGALRM
        previous_timer = signal.setitimer(signal.ITIMER_REAL, scope.timeout)

    try:
        yield cancel
    finally:
        if scope.timeout is not None:
            # Restore the previous timer
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)

        # Restore the previous signal handler
        signal.signal(signal.SIGALRM, previous_alarm_handler)


@contextlib.contextmanager
def _watcher_thread_based_timeout(scope: SyncCancelScope):
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
            with _get_thread_shield(supervised_thread):
                try:
                    _send_exception_to_thread(supervised_thread, exc)
                except ValueError:
                    # If the thread is gone; just move on without error
                    logger.debug("Thread missing!")

        # Wait for the supervised thread to exit its context
        logger.debug("Waiting for supervised thread to exit...")
        event.wait()

    def cancel():
        return _send_exception(CancelledError)

    def timeout_enforcer():
        if not event.wait(scope.timeout):
            logger.debug(
                "Cancel fired for watcher based timeout for thread %r and scope %r",
                supervised_thread.name,
                scope,
            )
            if scope.cancel(throw=False):
                with _get_thread_shield(supervised_thread):
                    cancel()

    if scope.timeout is not None:
        enforcer = threading.Thread(
            target=timeout_enforcer,
            name=f"timeout-watcher {scope.name or '<unnamed>'} {scope.timeout:.2f}",
        )
        enforcer.start()

    try:
        yield cancel
    finally:
        event.set()
        if enforcer:
            logger.debug("Joining enforcer thread %r", enforcer)
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
