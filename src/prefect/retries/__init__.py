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
    """
    A function that returns a wait calculator that produces exponentially increasing wait times.

    Args:
        base: The base wait time.
        max_wait: The maximum wait time.
        jitter: The jitter to apply to the wait time.

    Returns:
        A wait calculator that returns a wait time in seconds based on the attempt number.
    """

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
    """
    A function that returns a wait calculator that applies jitter to the provided wait time.

    Args:
        wait: The wait time to apply jitter to.
        jitter: The jitter to apply to the wait time.

    Returns:
        A wait calculator that returns a wait time in seconds based on the attempt number.
    """

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
    """
    A generator that can be used to retry a block of code.

    Args:
        attempts: The number of attempts to retry the block of code.
        wait: The wait time between attempts.
        should_retry: A function that determines whether the block of code should
            be retried.
        before_attempt: A function that is called before an attempt is made.
        on_success: A function that is called when an attempt is successful.
        on_failure: A function that is called when an attempt fails.
        before_wait: A function that is called before a wait is made between attempts.
        after_wait: A function that is called after a wait is made between attempts.
        on_attempts_exhausted: A function that is called when all attempts have been
            made and the block of code has not been successful.

    Yields:
        An attempt context that captures and handles exceptions for the wrapped
            code block.

    Example:
        ```python
        from prefect.retries import RetryBlock

        for attempt in RetryBlock(attempts=3):
            with attempt:
                if attempt.attempt < 2:
                    raise Exception("This is a test exception")
                else:
                    print("Success!")
        ```
    """

    def __init__(
        self,
        attempts: int = 3,
        wait: "float | WaitCalculator | WaitSequence" = 0.0,
        should_retry: "ShouldRetryCallback | bool" = True,
        before_attempt: "Sequence[BeforeAttemptCallback]" = tuple(),
        on_success: "Sequence[OnSuccessCallback]" = tuple(),
        on_failure: "Sequence[OnFailureCallback]" = tuple(),
        before_wait: "Sequence[BeforeWaitCallback]" = tuple(),
        after_wait: "Sequence[AfterWaitCallback]" = tuple(),
        on_attempts_exhausted: "Sequence[OnAttemptsExhaustedCallback]" = tuple(),
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

    def _handle_success(self, attempt: AttemptContext) -> None:
        for callback in self.on_success:
            callback(attempt.attempt, self.attempts)
        self._last_exception = None

    def _handle_exception(
        self,
        attempt: AttemptContext,
        exc_value: Exception,
    ) -> None:
        self._last_exception = exc_value
        for callback in self.on_failure:
            callback(exc_value, attempt.attempt, self.attempts)

    def __iter__(self) -> Iterator[AttemptContext]:
        return self

    def __next__(self) -> AttemptContext:
        attempt = next(self._attempt_iter)

        if attempt == 0:
            for callback in self.before_attempt:
                callback(attempt, self.attempts)
            return AttemptContext(
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
            for callback in self.before_wait:
                callback(self._last_exception, attempt, self.attempts, wait_time)
            time.sleep(wait_time)
            for callback in self.after_wait:
                callback(self._last_exception, attempt, self.attempts, wait_time)

            for callback in self.before_attempt:
                callback(attempt, self.attempts)
            return AttemptContext(
                attempt=attempt,
                on_success=self._handle_success,
                on_exception=self._handle_exception,
            )
        elif self._last_exception:
            for callback in self.on_attempts_exhausted:
                callback(self._last_exception, attempt, self.attempts, 0)
            raise self._last_exception
        else:
            raise StopIteration


class AttemptContextOnSuccessCallback(Protocol):
    """
    A function provided to an `AttemptContext` that is called when an attempt is successful.
    """

    def __call__(self, attempt: AttemptContext) -> None: ...


class AttemptContextOnExceptionCallback(Protocol):
    """
    A function provided to an `AttemptContext` that is called when an attempt fails.
    """

    def __call__(self, attempt: AttemptContext, exc_value: Exception) -> None: ...


class AttemptContext:
    """
    A context manager that captures and handles exceptions for a block of code.

    Args:
        attempt: The attempt number.
        on_success: A function that is called when an attempt is successful.
        on_exception: A function that is called when an attempt fails.
    """

    def __init__(
        self,
        attempt: int,
        on_success: AttemptContextOnSuccessCallback = NO_OP_CALLBACK,
        on_exception: AttemptContextOnExceptionCallback = NO_OP_CALLBACK,
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
    """
    A generator that can be used to retry a block of code.

    Args:
        attempts: The number of attempts to retry the block of code.
        wait: The wait time between attempts.
        should_retry: A function that determines whether the block of code should
            be retried.
        before_attempt: A function that is called before an attempt is made.
        on_success: A function that is called when an attempt is successful.
        on_failure: A function that is called when an attempt fails.
        before_wait: A function that is called before a wait is made between attempts.
        after_wait: A function that is called after a wait is made between attempts.
        on_attempts_exhausted: A function that is called when all attempts have been
            made and the block of code has not been successful.

    Yields:
        An attempt context that captures and handles exceptions for the wrapped
            code block.

    Example:
        ```python
        from prefect.retries import AsyncRetryBlock

        async for attempt in AsyncRetryBlock(attempts=3):
            with attempt:
                if attempt.attempt < 2:
                    raise Exception("This is a test exception")
                else:
                    print("Success!")
        ```
    """

    def __init__(
        self,
        attempts: int = 3,
        wait: float | WaitCalculator | WaitSequence = 0.0,
        should_retry: ShouldRetryCallback | bool = True,
        before_attempt: Sequence[
            BeforeAttemptCallback | AsyncBeforeAttemptCallback
        ] = tuple(),
        on_success: Sequence[OnSuccessCallback | AsyncOnSuccessCallback] = tuple(),
        on_failure: Sequence[OnFailureCallback | AsyncOnFailureCallback] = tuple(),
        before_wait: Sequence[BeforeWaitCallback | AsyncBeforeWaitCallback] = tuple(),
        after_wait: Sequence[AfterWaitCallback | AsyncAfterWaitCallback] = tuple(),
        on_attempts_exhausted: Sequence[
            OnAttemptsExhaustedCallback | AsyncOnAttemptsExhaustedCallback
        ] = tuple(),
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

    async def _handle_success(self, attempt: AsyncAttemptContext) -> None:
        self._last_exception = None
        for callback in self.on_success:
            if inspect.iscoroutinefunction(callback):
                await callback(attempt.attempt, self.attempts)
            else:
                callback(attempt.attempt, self.attempts)

    async def _handle_exception(
        self,
        attempt: AsyncAttemptContext,
        exc_value: Exception,
    ) -> None:
        self._last_exception = exc_value
        for callback in self.on_failure:
            if inspect.iscoroutinefunction(callback):
                await callback(exc_value, attempt.attempt, self.attempts)
            else:
                callback(exc_value, attempt.attempt, self.attempts)

    def __aiter__(self) -> AsyncIterator[AsyncAttemptContext]:
        return self

    async def __anext__(self) -> AsyncAttemptContext:
        attempt = next(self._attempt_iter)

        if attempt == 0:
            for callback in self.before_attempt:
                if inspect.iscoroutinefunction(callback):
                    await callback(attempt, self.attempts)
                else:
                    callback(attempt, self.attempts)

            return AsyncAttemptContext(
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
                for callback in self.before_wait:
                    if inspect.iscoroutinefunction(callback):
                        await callback(
                            self._last_exception, attempt, self.attempts, wait_time
                        )
                    else:
                        callback(
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
                for callback in self.after_wait:
                    if inspect.iscoroutinefunction(callback):
                        await callback(
                            self._last_exception, attempt, self.attempts, wait_time
                        )
                    else:
                        callback(
                            self._last_exception, attempt, self.attempts, wait_time
                        )

            if inspect.iscoroutinefunction(self.before_attempt):
                await self.before_attempt(attempt, self.attempts)
            else:
                for callback in self.before_attempt:
                    if inspect.iscoroutinefunction(callback):
                        await callback(attempt, self.attempts)
                    else:
                        callback(attempt, self.attempts)
            return AsyncAttemptContext(
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
                for callback in self.on_attempts_exhausted:
                    if inspect.iscoroutinefunction(callback):
                        await callback(self._last_exception, attempt, self.attempts, 0)
                    else:
                        callback(self._last_exception, attempt, self.attempts, 0)
            raise self._last_exception
        else:
            raise StopAsyncIteration


class AsyncAttemptOnSuccessCallback(Protocol):
    """
    A function provided to an `AsyncAttemptContext` that is called when an attempt is successful.
    """

    async def __call__(self, attempt: AsyncAttemptContext) -> None: ...


class AsyncAttemptOnExceptionCallback(Protocol):
    """
    A function provided to an `AsyncAttemptContext` that is called when an attempt fails.
    """

    async def __call__(
        self, attempt: AsyncAttemptContext, exc_value: Exception
    ) -> None: ...


class AsyncAttemptContext:
    """
    A context manager that captures and handles exceptions for a block of code.

    Args:
        attempt: The attempt number.
        on_success: A function that is called when an attempt is successful.
        on_exception: A function that is called when an attempt fails.
    """

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
    """
    A callable that will attempt to run without an exception for a specified
    number of attempts.

    You can easily create a Retriable instance by decorating a function with
        the `@retry` decorator.
    """

    def __init__(
        self,
        __fn: Callable[P, R],
        *,
        attempts: int = 3,
        wait: "float | WaitCalculator | WaitSequence" = 0.0,
        should_retry: "ShouldRetryCallback | bool" = True,
    ):
        self.__fn = __fn
        update_wrapper(self, __fn)

        self.attempts = attempts
        self.wait = wait
        self.should_retry = should_retry
        self.before_attempt_callbacks: "list[BeforeAttemptCallback]" = []
        self.on_success_callbacks: "list[OnSuccessCallback]" = []
        self.on_failure_callbacks: "list[OnFailureCallback]" = []
        self.before_wait_callbacks: "list[BeforeWaitCallback]" = []
        self.after_wait_callbacks: "list[AfterWaitCallback]" = []
        self.on_attempts_exhausted_callbacks: "list[OnAttemptsExhaustedCallback]" = []

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if inspect.iscoroutinefunction(self.__fn):
            return self._async_call(*args, **kwargs)  # pyright: ignore[reportReturnType] need to return a coroutine if the wrapped function is async
        else:
            for attempt in RetryBlock(
                self.attempts,
                self.wait,
                self.should_retry,
                self.before_attempt_callbacks,
                self.on_success_callbacks,
                self.on_failure_callbacks,
                self.before_wait_callbacks,
                self.after_wait_callbacks,
                self.on_attempts_exhausted_callbacks,
            ):
                with attempt:
                    return self.__fn(*args, **kwargs)

            raise RuntimeError("Attempts exhausted")

    async def _async_call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        async for attempt in AsyncRetryBlock(
            self.attempts,
            self.wait,
            self.should_retry,
            self.before_attempt_callbacks,
            self.on_success_callbacks,
            self.on_failure_callbacks,
            self.before_wait_callbacks,
            self.after_wait_callbacks,
            self.on_attempts_exhausted_callbacks,
        ):
            async with attempt:
                return await self.__fn(*args, **kwargs)

        raise RuntimeError("Attempts exhausted")

    def before_attempt(self, fn: BeforeAttemptCallback):
        """
        Register a function to be called before an attempt is made.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                return x + 1

            @my_function.before_attempt
            def before_attempt(attempt: int, attempts: int):
                print(f"Attempt {attempt} of {attempts}")
            ```
        """
        self.before_attempt_callbacks.append(fn)
        return self

    def on_success(self, fn: OnSuccessCallback):
        """
        Register a function to be called when an attempt is successful.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                return x + 1

            @my_function.on_success
            def on_success(attempt: int, attempts: int):
                print(f"Attempt {attempt} of {attempts} successful")
            ```
        """
        self.on_success_callbacks.append(fn)
        return self

    def on_failure(self, fn: OnFailureCallback):
        """
        Register a function to be called when an attempt fails.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                raise Exception("This is a test exception")

            @my_function.on_failure
            def on_failure(exc: Exception, attempt: int, attempts: int):
                print(f"Attempt {attempt} of {attempts} failed with exception {exc}")
            ```
        """
        self.on_failure_callbacks.append(fn)
        return self

    def before_wait(self, fn: BeforeWaitCallback):
        """
        Register a function to be called before a wait is made between attempts.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                raise Exception("This is a test exception")

            @my_function.before_wait
            def before_wait(exc: Exception, attempt: int, attempts: int, wait_time: float):
                print(f"Waiting {wait_time} seconds before attempt {attempt} of {attempts}")
            ```
        """
        self.before_wait_callbacks.append(fn)
        return self

    def after_wait(self, fn: AfterWaitCallback):
        """
        Register a function to be called after a wait is made between attempts.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                raise Exception("This is a test exception")

            @my_function.after_wait
            def after_wait(exc: Exception, attempt: int, attempts: int, wait_time: float):
                print(f"Waited {wait_time} seconds after attempt {attempt} of {attempts}")
            ```
        """
        self.after_wait_callbacks.append(fn)
        return self

    def on_attempts_exhausted(self, fn: OnAttemptsExhaustedCallback):
        """
        Register a function to be called when all attempts have been made and the function
            has not been successful.

        Example:
            ```python
            from prefect.retries import retry

            @retry(attempts=3)
            def my_function(x: int) -> int:
                raise Exception("This is a test exception")

            @my_function.on_attempts_exhausted
            def on_attempts_exhausted(exc: Exception, attempt: int, attempts: int, wait_time: float):
                print(f"All attempts exhausted with exception {exc}")
            ```
        """
        self.on_attempts_exhausted_callbacks.append(fn)
        return self


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
) -> Callable[[Callable[P, R]], Retriable[P, R]]: ...


def retry(
    __fn: Callable[P, R] | None = None,
    *,
    attempts: int = 3,
    wait: "float | WaitCalculator | WaitSequence" = 0.0,
    should_retry: "ShouldRetryCallback | bool" = True,
):
    """
    A decorator that will retry the wrapped function when it raises an exception.

    Example:
        ```python
        from prefect.retries import retry

        attempts = 0

        @retry(attempts=3)
        def my_function(x: int) -> int:
            global attempts
            attempts += 1
            if attempts < 3:
                raise Exception("This is a test exception")
            else:
                return x + 1

        my_function(1)
        ```
    """
    if __fn is None:
        return cast(
            Callable[[Callable[P, R]], Retriable[P, R]],
            partial(
                retry,
                attempts=attempts,
                wait=wait,
                should_retry=should_retry,
            ),
        )

    return Retriable(
        __fn,
        attempts=attempts,
        wait=wait,
        should_retry=should_retry,
    )
