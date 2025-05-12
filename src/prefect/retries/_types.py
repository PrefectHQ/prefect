from typing import Protocol, Sequence

WaitSequence = Sequence[float]


class WaitCalculator(Protocol):
    def __call__(self, attempt: int) -> float: ...


class ShouldRetryCallback(Protocol):
    def __call__(self, exc: Exception) -> bool: ...


class BeforeAttemptCallback(Protocol):
    def __call__(self, attempt: int, max_attempts: int): ...


class AsyncBeforeAttemptCallback(Protocol):
    async def __call__(self, attempt: int, max_attempts: int): ...


class OnSuccessCallback(Protocol):
    def __call__(self, attempt: int, max_attempts: int): ...


class AsyncOnSuccessCallback(Protocol):
    async def __call__(self, attempt: int, max_attempts: int): ...


class OnFailureCallback(Protocol):
    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncOnFailureCallback(Protocol):
    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class BeforeWaitCallback(Protocol):
    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncBeforeWaitCallback(Protocol):
    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AfterWaitCallback(Protocol):
    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncAfterWaitCallback(Protocol):
    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class OnAttemptsExhaustedCallback(Protocol):
    def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...


class AsyncOnAttemptsExhaustedCallback(Protocol):
    async def __call__(
        self, exc: Exception, attempt: int, max_attempts: int, wait_time: float
    ): ...
