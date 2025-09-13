from __future__ import annotations

import datetime
from collections.abc import Awaitable
from functools import partial, update_wrapper
from inspect import iscoroutinefunction
from typing import (
    TYPE_CHECKING,
    Callable,
    Generic,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import ParamSpec

from prefect.retries._attempts import (
    AsyncAttemptGenerator,
    AttemptGenerator,
)
from prefect.retries._protocols import AsyncAttemptHook, AttemptHook, WaitTimeProvider
from prefect.retries.stop_conditions import StopCondition

P = ParamSpec("P")
R = TypeVar("R")
H = TypeVar("H", bound=Union[AttemptHook, AsyncAttemptHook])


class Retriable(Generic[P, R]):
    """
    A callable that retries a function until a stop condition is met.

    In most cases, you should use the `@retry` decorator instead of instantiating this
    class directly.

    Args:
        __fn: The function to retry on failure.
        until: A `StopCondition` that determines when to stop retrying the provided
            function.
        wait: A `datetime.timedelta`, a number of seconds, or a callable that takes an
            AttemptContext and returns a timedelta, seconds, or None.
    """

    def __init__(
        self,
        __fn: Callable[P, R],
        *,
        until: StopCondition | None = None,
        wait: datetime.timedelta | int | float | None | WaitTimeProvider = None,
    ):
        self.fn = __fn
        update_wrapper(self, __fn)
        self.until = until
        self.wait = wait
        self.before_attempt_hooks: list[AttemptHook | AsyncAttemptHook] = []
        self.on_success_hooks: list[AttemptHook | AsyncAttemptHook] = []
        self.on_failure_hooks: list[AttemptHook | AsyncAttemptHook] = []
        self.before_wait_hooks: list[AttemptHook | AsyncAttemptHook] = []
        self.after_wait_hooks: list[AttemptHook | AsyncAttemptHook] = []

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if iscoroutinefunction(self.fn):
            return self._call_async(*args, **kwargs)  # pyright: ignore[reportReturnType]

        for attempt in AttemptGenerator(
            until=self.until,
            wait=self.wait,
            before_attempt=self.before_attempt_hooks,
            on_success=self.on_success_hooks,
            on_failure=self.on_failure_hooks,
            before_wait=self.before_wait_hooks,
            after_wait=self.after_wait_hooks,
        ):
            with attempt:
                result = self.fn(*args, **kwargs)
                attempt.result = result
                return result

        raise RuntimeError(
            "Failed to make a single attempt with the given stop condition"
        )

    def _call_async(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        async def _call() -> R:
            async for attempt in AsyncAttemptGenerator(
                until=self.until,
                wait=self.wait,
                before_attempt=self.before_attempt_hooks,
                on_success=self.on_success_hooks,
                on_failure=self.on_failure_hooks,
                before_wait=self.before_wait_hooks,
                after_wait=self.after_wait_hooks,
            ):
                async with attempt:
                    if TYPE_CHECKING:
                        assert iscoroutinefunction(self.fn)  # pragma: no cover

                    result = await self.fn(*args, **kwargs)
                    attempt.result = result
                    return result

            raise RuntimeError(
                "Failed to make a single attempt with the given stop condition"
            )

        return _call()

    def before_attempt(self, hook: H) -> H:
        """
        Add a hook that will be called before each attempt.

        Example:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3))
        def f(x: int) -> int:
            return x * 3

        @f.before_attempt
        def before_attempt(state: AttemptState):
            print(f"Attempt {state.attempt} started")
        ```
        """
        self.before_attempt_hooks.append(hook)
        return hook

    def on_success(self, hook: H) -> H:
        """
        Add a hook that will be called when the wrapped function succeeds.

        Example:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3))
        def f(x: int) -> int:
            return x * 3

        @f.on_success
        def on_success(state: AttemptState):
            print(f"Attempt {state.attempt} succeeded")
        """
        self.on_success_hooks.append(hook)
        return hook

    def on_failure(self, hook: H) -> H:
        """
        Add a hook that will be called when the wrapped function fails.

        Example:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3))
        def f(x: int) -> int:
            raise RuntimeError()

        @f.on_failure
        def on_failure(state: AttemptState):
            print(f"Attempt {state.attempt} failed")
        ```
        """
        self.on_failure_hooks.append(hook)
        return hook

    def before_wait(self, hook: H) -> H:
        """
        Add a hook that will be called before each wait.

        Example:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3), wait=5)
        def f(x: int) -> int:
            raise RuntimeError()

        @f.before_wait
        def before_wait(state: AttemptState):
            print(f"Waiting before next attempt")
        ```
        """
        self.before_wait_hooks.append(hook)
        return hook

    def after_wait(self, hook: H) -> H:
        """
        Add a hook that will be called after each wait.

        Example:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3), wait=5)
        def f(x: int) -> int:
            raise RuntimeError()

        @f.after_wait
        def after_wait(state: AttemptState):
            print(f"Finished waiting")
        ```
        """
        self.after_wait_hooks.append(hook)
        return hook


@overload
def retry(
    __fn: None = None,
    *,
    until: StopCondition | None = None,
    wait: datetime.timedelta | int | float | None | WaitTimeProvider = None,
) -> Callable[[Callable[P, R]], Retriable[P, R]]: ...


@overload
def retry(
    __fn: Callable[P, R],
    *,
    until: StopCondition | None = None,
    wait: datetime.timedelta | int | float | None | WaitTimeProvider = None,
) -> Retriable[P, R]: ...


def retry(
    __fn: Callable[P, R] | None = None,
    *,
    until: StopCondition | None = None,
    wait: datetime.timedelta | int | float | None | WaitTimeProvider = None,
) -> Retriable[P, R] | Callable[[Callable[P, R]], Retriable[P, R]]:
    """
    A function decorator that retries a function until a stop condition is met.

    Args:
        until: A `StopCondition` that determines when to stop retrying the provided
            function.
        wait: A `datetime.timedelta`, a number of seconds, or a callable that takes an
            AttemptContext and returns a timedelta, seconds, or None.

    Examples:
        Retry a function until 3 attempts have been made:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3))
        def f(x: int) -> int:
            return x * 3
        ```

        Retry a function until 3 attempts have been made, waiting 5 seconds between
        attempts:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted

        @retry(until=AttemptsExhausted(3), wait=5)
        def f(x: int) -> int:
            return x * 3
        ```

        Retry a function with exponential backoff (doubling wait each time, up to 60s):
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import AttemptsExhausted
        import datetime

        def exp_backoff(ctx):
            return min(2 ** (ctx.attempt - 1), 60)

        @retry(until=AttemptsExhausted(5), wait=exp_backoff)
        def f(x: int) -> int:
            return x * 3
        ```

        Retry a function as long as the raised exception is not a `ValueError`:
        ```python
        from prefect.retries import retry
        from prefect.retries.stop_conditions import ExceptionMatches

        @retry(until=~ExceptionMatches(ValueError))
        def f(x: int) -> int:
            return x * 3
        ```
    """
    if __fn is None:
        return cast(
            Callable[
                [Callable[P, R]],
                Retriable[P, R],
            ],
            partial(retry, until=until, wait=wait),
        )
    return Retriable(__fn, until=until, wait=wait)
