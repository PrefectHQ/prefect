import asyncio
from functools import wraps
from typing import Callable, Optional, Tuple, Type, TypeVar

from typing_extensions import ParamSpec

from prefect._internal._logging import logger
from prefect.utilities.math import clamped_poisson_interval

P = ParamSpec("P")
R = TypeVar("R")


def exponential_backoff_with_jitter(
    attempt: int, base_delay: float, max_delay: float
) -> float:
    average_interval = min(base_delay * (2**attempt), max_delay)
    return clamped_poisson_interval(average_interval, clamping_factor=0.3)


def retry_async_fn(
    max_attempts: int = 3,
    backoff_strategy: Callable[
        [int, float, float], float
    ] = exponential_backoff_with_jitter,
    base_delay: float = 1,
    max_delay: float = 10,
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    operation_name: Optional[str] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """A decorator for retrying an async function.

    Args:
        max_attempts: The maximum number of times to retry the function.
        backoff_strategy: A function that takes in the number of attempts, the base
            delay, and the maximum delay, and returns the delay to use for the next
            attempt. Defaults to an exponential backoff with jitter.
        base_delay: The base delay to use for the first attempt.
        max_delay: The maximum delay to use for the last attempt.
        retry_on_exceptions: A tuple of exception types to retry on. Defaults to
            retrying on all exceptions.
        operation_name: Optional name to use for logging the operation instead of
            the function name. If None, uses the function name.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            name = operation_name or func.__name__
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retry_on_exceptions as e:
                    if attempt == max_attempts - 1:
                        logger.exception(
                            f"Function {name!r} failed after {max_attempts} attempts"
                        )
                        raise
                    delay = backoff_strategy(attempt, base_delay, max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1} of function {name!r} failed with {type(e).__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator
