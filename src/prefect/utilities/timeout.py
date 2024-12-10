from asyncio import CancelledError
from contextlib import contextmanager
from typing import Optional

from prefect._internal.concurrency.cancellation import (
    cancel_async_after,
    cancel_sync_after,
)


def fail_if_not_timeout_error(timeout_exc_type: type[Exception]) -> None:
    if not issubclass(timeout_exc_type, TimeoutError):
        raise ValueError(
            "The `timeout_exc_type` argument must be a subclass of `TimeoutError`."
        )


@contextmanager
def timeout_async(
    seconds: Optional[float] = None, timeout_exc_type: type[TimeoutError] = TimeoutError
):
    fail_if_not_timeout_error(timeout_exc_type)

    if seconds is None:
        yield
        return

    try:
        with cancel_async_after(timeout=seconds):
            yield
    except CancelledError:
        raise timeout_exc_type(f"Scope timed out after {seconds} second(s).")


@contextmanager
def timeout(
    seconds: Optional[float] = None, timeout_exc_type: type[TimeoutError] = TimeoutError
):
    fail_if_not_timeout_error(timeout_exc_type)

    if seconds is None:
        yield
        return

    try:
        with cancel_sync_after(timeout=seconds):
            yield
    except CancelledError:
        raise timeout_exc_type(f"Scope timed out after {seconds} second(s).")
