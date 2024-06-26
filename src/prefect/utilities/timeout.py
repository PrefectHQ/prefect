from asyncio import CancelledError
from contextlib import contextmanager
from typing import Optional, Type

from prefect._internal.concurrency.cancellation import (
    cancel_async_after,
    cancel_sync_after,
)


@contextmanager
def timeout_async(
    seconds: Optional[float] = None, timeout_exc_type: Type[TimeoutError] = TimeoutError
):
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
    seconds: Optional[float] = None, timeout_exc_type: Type[TimeoutError] = TimeoutError
):
    if seconds is None:
        yield
        return

    try:
        with cancel_sync_after(timeout=seconds):
            yield
    except CancelledError:
        raise timeout_exc_type(f"Scope timed out after {seconds} second(s).")
