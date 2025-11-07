"""Testing utilities for internal use."""

import asyncio
from typing import Any, AsyncIterator

from typing_extensions import Self


class AssertionRetryAttempt:
    """Context manager for capturing exceptions during retry attempts."""

    def __init__(self, attempt_number: int):
        self.attempt_number = attempt_number
        self.exception: Exception | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if exc_val is not None:
            self.exception = exc_val  # type: ignore
        return exc_type is AssertionError


async def retry_asserts(
    max_attempts: int = 3,
    delay: float = 1.0,
) -> AsyncIterator[AssertionRetryAttempt]:
    """
    Async generator that retries a block of assertions until it succeeds or max attempts is reached.

    Useful for testing eventual consistency scenarios where changes may not
    propagate immediately.

    Args:
        max_attempts: Maximum number of attempts before raising the exception.
        delay: Time in seconds to wait between retry attempts.

    Yields:
        A context manager that captures exceptions during each attempt.

    Raises:
        The last exception raised within the block if all attempts fail.

    Example:
        ```python
        async for attempt in retry_asserts(max_attempts=3):
            with attempt:
                for deployment in deployments:
                    await session.refresh(deployment)
                    assert deployment.status == DeploymentStatus.READY
        ```
    """
    for attempt_number in range(1, max_attempts + 1):
        attempt = AssertionRetryAttempt(attempt_number)
        yield attempt

        if attempt.exception is None:
            return  # Success, exit early

        if attempt_number == max_attempts:
            raise attempt.exception

        await asyncio.sleep(delay)
