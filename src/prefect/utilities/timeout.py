from contextlib import asynccontextmanager, contextmanager
from typing import Optional

from prefect._internal.concurrency.cancellation import (
    AlarmCancelScope,
    AsyncCancelScope,
    CancelledError,
)


@asynccontextmanager
async def timeout_async(seconds: Optional[float] = None):
    try:
        with AsyncCancelScope(timeout=seconds):
            yield
    except CancelledError:
        raise TimeoutError(f"Scope timed out after {seconds} second(s).")


@contextmanager
def timeout(seconds: Optional[float] = None):
    try:
        with AlarmCancelScope(timeout=seconds):
            yield
    except CancelledError:
        raise TimeoutError(f"Scope timed out after {seconds} second(s).")
