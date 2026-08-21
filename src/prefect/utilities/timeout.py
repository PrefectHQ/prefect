import asyncio
from contextlib import contextmanager, suppress
from typing import AsyncIterator, Optional

def fail_if_not_timeout_error(timeout_exc_type: type[Exception]) -> None:
    if not issubclass(timeout_exc_type, TimeoutError):
        raise ValueError(
            "The `timeout_exc_type` argument must be a subclass of `TimeoutError`."
        )


from contextlib import asynccontextmanager

@asynccontextmanager
async def timeout_async(
    seconds: Optional[float] = None, timeout_exc_type: type[TimeoutError] = TimeoutError
):
    fail_if_not_timeout_error(timeout_exc_type)

    if seconds is None:
        yield
        return

    if timeout_exc_type is TimeoutError:
        # Use asyncio's built-in timeout, which is robust and raises TimeoutError.
        try:
            async with asyncio.timeout(seconds):
                yield
        except TimeoutError:
            raise
    else:
        # For custom subclasses, wrap the built-in timeout and re-raise with custom type.
        try:
            async with asyncio.timeout(seconds):
                yield
        except TimeoutError:
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
