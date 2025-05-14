"""
This module contains the types for the retries module.
"""

from typing import Protocol, Sequence

WaitSequence = Sequence[float]


class WaitCalculator(Protocol):
    """
    A function that takes an attempt number and returns a wait time.
    """

    def __call__(self, attempt: int) -> float: ...


class ShouldRetryCallback(Protocol):
    """
    A function that takes an exception and returns a boolean indicating
    whether the function should be retried.
    """

    def __call__(self, exc: Exception) -> bool: ...


class BeforeAttemptCallback(Protocol):
    """
    A function that is called before an attempt is made.
    """

    def __call__(self, attempt: int, max_attempts: int): ...


class AsyncBeforeAttemptCallback(Protocol):
    """
    An async function that is called before an attempt is made.
    """

    async def __call__(self, attempt: int, max_attempts: int): ...


class OnSuccessCallback(Protocol):
    """
    A function that is called when an attempt is successful.
    """

    def __call__(self, attempt: int, max_attempts: int): ...


class AsyncOnSuccessCallback(Protocol):
    """
    An async function that is called when an attempt is successful.
    """

    async def __call__(self, attempt: int, max_attempts: int): ...


class OnFailureCallback(Protocol):
    """
    A function that is called when an attempt fails.
    """

    def __call__(self, exc: Exception, attempt: int, max_attempts: int): ...


class AsyncOnFailureCallback(Protocol):
    """
    An async function that is called when an attempt fails.
    """

    async def __call__(self, exc: Exception, attempt: int, max_attempts: int): ...


class BeforeWaitCallback(Protocol):
    """
    A function that is called before a wait is made between attempts.
    """

    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncBeforeWaitCallback(Protocol):
    """
    An async function that is called before a wait is made between attempts.
    """

    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AfterWaitCallback(Protocol):
    """
    A function that is called after a wait is made between attempts.
    """

    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncAfterWaitCallback(Protocol):
    """
    An async function that is called after a wait is made between attempts.
    """

    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class OnAttemptsExhaustedCallback(Protocol):
    """
    A function that is called when all attempts have been made and the function
    has not been successful.
    """

    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncOnAttemptsExhaustedCallback(Protocol):
    """
    An async function that is called when all attempts have been made and the function
    has not been successful.
    """

    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...
