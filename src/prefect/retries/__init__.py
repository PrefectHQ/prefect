from __future__ import annotations

import asyncio
import inspect
import time
from functools import partial, update_wrapper
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Generic,
    Iterator,
    Protocol,
    Sequence,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import ParamSpec


from prefect.utilities.math import clamped_poisson_interval

if TYPE_CHECKING:
    from prefect.retries._types import (
        OnFailureCallback,
        OnSuccessCallback,
        AsyncOnFailureCallback,
        AsyncOnSuccessCallback,
        AsyncBeforeAttemptCallback,
        AsyncAfterWaitCallback,
        BeforeAttemptCallback,
        ShouldRetryCallback,
        WaitCalculator,
        AfterWaitCallback,
        WaitSequence,
        BeforeWaitCallback,
        AsyncBeforeWaitCallback,
        OnAttemptsExhaustedCallback,
        AsyncOnAttemptsExhaustedCallback,
    )

P = ParamSpec("P")
R = TypeVar("R")


def exponential_backoff(
    base: float = 0.0, max_wait: float = 10.0, jitter: float = 0.0
) -> WaitCalculator:
    def wait(attempt: int) -> float:
        average_interval = min(base * (2**attempt), max_wait)
        if jitter > 0:
            return clamped_poisson_interval(average_interval, clamping_factor=jitter)
        else:
            return average_interval

    return wait


def wait_with_jitter(
    wait: int | float | WaitSequence, jitter: float = 0.0
) -> WaitCalculator:
    def wait_calculator(attempt: int) -> float:
        nonlocal wait
        if isinstance(wait, Sequence):
            if len(wait) <= attempt - 1:
                base_wait = wait[-1]
            else:
                base_wait = wait[attempt - 1]
        else:
            base_wait = wait

        if jitter > 0:
            return clamped_poisson_interval(base_wait, clamping_factor=jitter)
        else:
            return base_wait

    return wait_calculator


def NO_OP_CALLBACK(*args: Any, **kwargs: Any):
    pass  # pragma: no cover


async def NO_OP_ASYNC_CALLBACK(*args: Any, **kwargs: Any) -> None:
    pass  # pragma: no cover


class RetryBlock(Generic[P, R]):
    def __init__(
        self,
        attempts: int = 3,
        wait: "float | WaitCalculator | WaitSequence" = 0.0,
        should_retry: "ShouldRetryCallback | bool" = True,
        before_attempt: "BeforeAttemptCallback" = NO_OP_CALLBACK,
        on_success: "OnSuccessCallback" = NO_OP_CALLBACK,
        on_failure: "OnFailureCallback" = NO_OP_CALLBACK,
        before_wait: "BeforeWaitCallback" = NO_OP_CALLBACK,
        after_wait: "AfterWaitCallback" = NO_OP_CALLBACK,
        on_attempts_exhausted: "OnAttemptsExhaustedCallback" = NO_OP_CALLBACK,
    ):
        if attempts < 1:
            raise ValueError("attempts must be a positive integer")

        self.attempts = attempts
        self.wait = wait
        self.should_retry = should_retry
        self.before_attempt = before_attempt
        self.on_success = on_success
        self.on_failure = on_failure
        self.before_wait = before_wait
        self.after_wait = after_wait
        self.on_attempts_exhausted = on_attempts_exhausted
        self._attempt_iter = iter(range(attempts + 1))
        self._last_exception: Exception | None = None

    def _handle_success(self, attempt: Attempt) -> None:
        self.on_success(attempt.attempt, self.attempts)
        self._last_exception = None

    def _handle_exception(
        self,
        attempt: Attempt,
        exc_value: Exception,
    ) -> None:
        self._last_exception = exc_value
        self.on_failure(exc_value, attempt.attempt, self.attempts, 0)

    def __iter__(self) -> Iterator[Attempt]:
        return self

    def __next__(self) -> Attempt:
        attempt = next(self._attempt_iter)

        if attempt == 0:
            self.before_attempt(attempt, self.attempts)
            return Attempt(
                attempt=attempt,
                on_success=self._handle_success,
                on_exception=self._handle_exception,
            )

        should_retry = (
            self._last_exception
            and (
                self.should_retry(self._last_exception)
                if callable(self.should_retry)
                else self.should_retry
            )
            and attempt < self.attempts
        )

        if should_retry:
            if callable(self.wait):
                wait_time = self.wait(attempt)
            elif isinstance(self.wait, Sequence):
                if len(self.wait) <= attempt - 1:
                    wait_time = self.wait[-1]
                else:
                    wait_time = self.wait[attempt - 1]
            else:
                wait_time = self.wait
            if TYPE_CHECKING:
                assert self._last_exception is not None
            self.before_wait(self._last_exception, attempt, self.attempts, wait_time)
            time.sleep(wait_time)
            self.after_wait(self._last_exception, attempt, self.attempts, wait_time)

            self.before_attempt(attempt, self.attempts)
            return Attempt(
                attempt=attempt,
                on_success=self._handle_success,
                on_exception=self._handle_exception,
            )
        elif self._last_exception:
            self.on_attempts_exhausted(self._last_exception, attempt, self.attempts, 0)
            raise self._last_exception
        else:
            raise StopIteration


class AttemptOnSuccessCallback(Protocol):
    def __call__(self, attempt: Attempt) -> None: ...


class AttemptOnExceptionCallback(Protocol):
    def __call__(self, attempt: Attempt, exc_value: Exception) -> None: ...


class Attempt:
    def __init__(
        self,
        attempt: int,
        on_success: AttemptOnSuccessCallback = NO_OP_CALLBACK,
        on_exception: AttemptOnExceptionCallback = NO_OP_CALLBACK,
    ):
        self.attempt = attempt
        self.on_success = on_success
        self.on_exception = on_exception

    def __enter__(self) -> None:
        pass

    def __exit__(
        self,
        exc_type: type[Exception] | None,
        exc_value: Exception | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_value is None:
            self.on_success(self)
            return True
        else:
            self.on_exception(self, exc_value)
            return True


class AsyncRetryBlock(Generic[P, R]):
    def __init__(
        self,
        attempts: int = 3,
        wait: float | WaitCalculator | WaitSequence = 0.0,
        should_retry: ShouldRetryCallback | bool = True,
        before_attempt: BeforeAttemptCallback
        | AsyncBeforeAttemptCallback = NO_OP_CALLBACK,
        on_success: OnSuccessCallback | AsyncOnSuccessCallback = NO_OP_CALLBACK,
        on_failure: OnFailureCallback | AsyncOnFailureCallback = NO_OP_CALLBACK,
        before_wait: BeforeWaitCallback | AsyncBeforeWaitCallback = NO_OP_CALLBACK,
        after_wait: AfterWaitCallback | AsyncAfterWaitCallback = NO_OP_CALLBACK,
        on_attempts_exhausted: OnAttemptsExhaustedCallback
        | AsyncOnAttemptsExhaustedCallback = NO_OP_CALLBACK,
    ):
        self.attempts = attempts
        self.wait = wait
        self.should_retry = should_retry
        self.before_attempt = before_attempt
        self.on_success = on_success
        self.on_failure = on_failure
        self.before_wait = before_wait
        self.after_wait = after_wait
        self.on_attempts_exhausted = on_attempts_exhausted
        self._attempt_iter = iter(range(attempts + 1))

    async def _handle_success(self, attempt: AsyncAttempt) -> None:
        self._last_exception = None
        if inspect.iscoroutinefunction(self.on_success):
            await self.on_success(attempt.attempt, self.attempts)
        else:
            self.on_success(attempt.attempt, self.attempts)

    async def _handle_exception(
        self,
        attempt: AsyncAttempt,
        exc_value: Exception,
    ) -> None:
        self._last_exception = exc_value
        if inspect.iscoroutinefunction(self.on_failure):
            await self.on_failure(exc_value, attempt.attempt, self.attempts, 0)
        else:
            self.on_failure(exc_value, attempt.attempt, self.attempts, 0)

    def __aiter__(self) -> AsyncIterator[AsyncAttempt]:
        return self

    async def __anext__(self) -> AsyncAttempt:
        try:
            attempt = next(self._attempt_iter)
        except StopIteration:
            raise StopAsyncIteration

        if attempt == 0:
            if inspect.iscoroutinefunction(self.before_attempt):
                await self.before_attempt(attempt, self.attempts)
            else:
                self.before_attempt(attempt, self.attempts)
            return AsyncAttempt(
                attempt=attempt,
                on_success=self._handle_success,
                on_exception=self._handle_exception,
            )

        should_retry = (
            self._last_exception
            and (
                self.should_retry(self._last_exception)
                if callable(self.should_retry)
                else self.should_retry
            )
            and attempt < self.attempts
        )

        if should_retry:
            if callable(self.wait):
                wait_time = self.wait(attempt)
            elif isinstance(self.wait, Sequence):
                if len(self.wait) <= attempt:
                    wait_time = self.wait[-1]
                else:
                    wait_time = self.wait[attempt]
            else:
                wait_time = self.wait
            if TYPE_CHECKING:
                assert self._last_exception is not None
            if inspect.iscoroutinefunction(self.before_wait):
                await self.before_wait(
                    self._last_exception, attempt, self.attempts, wait_time
                )
            else:
                self.before_wait(
                    self._last_exception, attempt, self.attempts, wait_time
                )
            await asyncio.sleep(wait_time)
            if TYPE_CHECKING:
                assert self._last_exception is not None

            if inspect.iscoroutinefunction(self.after_wait):
                await self.after_wait(
                    self._last_exception, attempt, self.attempts, wait_time
                )
            else:
                self.after_wait(self._last_exception, attempt, self.attempts, wait_time)

            if inspect.iscoroutinefunction(self.before_attempt):
                await self.before_attempt(attempt, self.attempts)
            else:
                self.before_attempt(attempt, self.attempts)
            return AsyncAttempt(
                attempt=attempt,
                on_success=self._handle_success,
                on_exception=self._handle_exception,
            )
        elif self._last_exception:
            if inspect.iscoroutinefunction(self.on_attempts_exhausted):
                await self.on_attempts_exhausted(
                    self._last_exception, attempt, self.attempts, 0
                )
            else:
                self.on_attempts_exhausted(
                    self._last_exception, attempt, self.attempts, 0
                )
            raise self._last_exception
        else:
            raise StopAsyncIteration


class AsyncAttemptOnSuccessCallback(Protocol):
    async def __call__(self, attempt: AsyncAttempt) -> None: ...


class AsyncAttemptOnExceptionCallback(Protocol):
    async def __call__(self, attempt: AsyncAttempt, exc_value: Exception) -> None: ...


class AsyncAttempt:
    def __init__(
        self,
        attempt: int,
        on_success: AsyncAttemptOnSuccessCallback = NO_OP_ASYNC_CALLBACK,
        on_exception: AsyncAttemptOnExceptionCallback = NO_OP_ASYNC_CALLBACK,
    ):
        self.attempt = attempt
        self.on_success = on_success
        self.on_exception = on_exception

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc_value: Exception | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_value is None:
            await self.on_success(self)
            return True
        else:
            await self.on_exception(self, exc_value)
            return True


class Retriable(Generic[P, R]):
    def __init__(
        self,
        __fn: Callable[P, R],
        *,
        attempts: int = 3,
        wait: "float | WaitCalculator | WaitSequence" = 0.0,
        should_retry: "ShouldRetryCallback | bool" = True,
        before_attempt: "BeforeAttemptCallback" = NO_OP_CALLBACK,
        on_success: "OnSuccessCallback" = NO_OP_CALLBACK,
        on_failure: "OnFailureCallback" = NO_OP_CALLBACK,
        before_wait: "BeforeWaitCallback" = NO_OP_CALLBACK,
        after_wait: "AfterWaitCallback" = NO_OP_CALLBACK,
        on_attempts_exhausted: "OnAttemptsExhaustedCallback" = NO_OP_CALLBACK,
    ):
        self.__fn = __fn
        update_wrapper(self, __fn)

        self.attempts = attempts
        self.wait = wait
        self.should_retry = should_retry
        self.before_attempt = before_attempt
        self.on_success = on_success
        self.on_failure = on_failure
        self.before_wait = before_wait
        self.after_wait = after_wait

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if inspect.iscoroutinefunction(self.__fn):
            return self._async_call(*args, **kwargs)  # pyright: ignore[reportReturnType] need to return a coroutine if the wrapped function is async
        else:
            for attempt in RetryBlock(
                self.attempts,
                self.wait,
                self.should_retry,
                self.before_attempt,
                self.on_success,
                self.on_failure,
                self.before_wait,
                self.after_wait,
            ):
                with attempt:
                    return self.__fn(*args, **kwargs)

            raise RuntimeError("Attempts exhausted")

    async def _async_call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        async for attempt in AsyncRetryBlock(
            self.attempts,
            self.wait,
            self.should_retry,
            self.before_attempt,
            self.on_success,
            self.on_failure,
            self.before_wait,
            self.after_wait,
        ):
            async with attempt:
                return await self.__fn(*args, **kwargs)

        raise RuntimeError("Attempts exhausted")


@overload
def retry(
    __fn: Callable[P, R],
) -> Retriable[P, R]: ...


@overload
def retry(
    __fn: None = None,
    *,
    attempts: int = 3,
    wait: "float | WaitCalculator | WaitSequence" = 0.0,
    should_retry: "ShouldRetryCallback | bool" = True,
    before_attempt: "BeforeAttemptCallback" = NO_OP_CALLBACK,
    on_success: "OnSuccessCallback" = NO_OP_CALLBACK,
    on_failure: "OnFailureCallback" = NO_OP_CALLBACK,
    before_wait: "BeforeWaitCallback" = NO_OP_CALLBACK,
    after_wait: "AfterWaitCallback" = NO_OP_CALLBACK,
) -> Callable[[Callable[P, R]], Retriable[P, R]]: ...


def retry(
    __fn: Callable[P, R] | None = None,
    *,
    attempts: int = 3,
    wait: "float | WaitCalculator | WaitSequence" = 0.0,
    should_retry: "ShouldRetryCallback | bool" = True,
    before_attempt: "BeforeAttemptCallback" = NO_OP_CALLBACK,
    on_success: "OnSuccessCallback" = NO_OP_CALLBACK,
    on_failure: "OnFailureCallback" = NO_OP_CALLBACK,
    before_wait: "BeforeWaitCallback" = NO_OP_CALLBACK,
    after_wait: "AfterWaitCallback" = NO_OP_CALLBACK,
):
    if __fn is None:
        return cast(
            Callable[[Callable[P, R]], Retriable[P, R]],
            partial(
                retry,
                attempts=attempts,
                wait=wait,
                should_retry=should_retry,
                before_attempt=before_attempt,
                on_success=on_success,
                on_failure=on_failure,
                before_wait=before_wait,
                after_wait=after_wait,
            ),
        )

    return Retriable(
        __fn,
        attempts=attempts,
        wait=wait,
        should_retry=should_retry,
        before_attempt=before_attempt,
        on_success=on_success,
        on_failure=on_failure,
        before_wait=before_wait,
        after_wait=after_wait,
    )
