from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from prefect.retries import Retriable, retry
from prefect.retries._dataclasses import AttemptState, Phase
from prefect.retries.stop_conditions import AttemptsExhausted, StopCondition


def always_succeeds(x: int) -> int:
    return x * 2


def sometimes_fails(x: int) -> int:
    """
    Sometimes fails with a ValueError.
    """
    if x < 0:
        raise ValueError("Negative!")
    return x


class TestRetriable:
    def test_retriable_success(self):
        r = Retriable(always_succeeds, until=AttemptsExhausted(3))
        assert r(5) == 10

    def test_retriable_failure(self):
        r = Retriable(
            lambda: (_ for _ in ()).throw(ValueError()), until=AttemptsExhausted(2)
        )
        with pytest.raises(ValueError):
            r()

    def test_retriable_eventual_success(self):
        attempts = 0

        def fn(x: int) -> int:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise Exception("fail")
            return x

        r = Retriable(fn, until=AttemptsExhausted(3))
        assert r(42) == 42
        assert attempts == 2

    def test_retriable_wraps_callable(self):
        r = Retriable(sometimes_fails, until=AttemptsExhausted(3))
        assert getattr(r, "__wrapped__", None) is sometimes_fails
        assert getattr(r, "__name__", None) == "sometimes_fails"
        assert getattr(r, "__doc__", None) == sometimes_fails.__doc__


class TestRetryDecorator:
    class TestSync:
        def test_retry_decorator_success(self):
            @retry(until=AttemptsExhausted(2))
            def f(x: int) -> int:
                return x + 1

            assert f(2) == 3

        def test_retry_decorator_eventual_success(self):
            attempts = 0

            @retry(until=AttemptsExhausted(3))
            def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise Exception("fail")
                return x

            assert f(7) == 7
            assert attempts == 2

        def test_retry_decorator_no_until(self):
            @retry
            def f(x: int) -> int:
                return x * 3

            assert f(3) == 9

        def test_retry_with_invalid_stop_condition(self):
            class NeverAttempt(StopCondition):
                def is_met(self, context: AttemptState | None) -> bool:  # noqa: ARG002
                    return True

            @retry(until=NeverAttempt())
            def f(x: int) -> int:
                return x * 3

            with pytest.raises(
                RuntimeError,
                match="Failed to make a single attempt with the given stop condition",
            ):
                f(3)

        @pytest.mark.parametrize("wait", [5, datetime.timedelta(minutes=5), 5.0])
        def test_retry_decorator_with_wait(
            self, wait: int | float | datetime.timedelta, mock_sleep: MagicMock
        ):
            attempts = 0

            @retry(until=AttemptsExhausted(3), wait=wait)
            def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise Exception("fail")
                return x * 3

            assert f(3) == 9

            if isinstance(wait, datetime.timedelta):
                mock_sleep.assert_called_once_with(wait.total_seconds())
            else:
                mock_sleep.assert_called_once_with(wait)

        def test_retry_decorator_with_exponential_backoff_callable(
            self, mock_sleep: MagicMock
        ):
            attempts = 0

            def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
                return 2 ** (next.attempt - 1)

            @retry(until=AttemptsExhausted(4), wait=exp_backoff)
            def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise Exception("fail")
                return x

            assert f(5) == 5
            # Should sleep 2, 4, 8 seconds (for attempts 2, 3, 4)
            mock_sleep.assert_has_calls(
                [
                    call(2),
                    call(4),
                    call(8),
                ]
            )

        def test_retry_decorator_with_exponential_backoff_callable_and_max_wait(
            self, mock_sleep: MagicMock
        ):
            attempts = 0

            def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
                return min(3 ** (next.attempt - 1), 7)

            @retry(until=AttemptsExhausted(5), wait=exp_backoff)
            def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 5:
                    raise Exception("fail")
                return x

            assert f(10) == 10
            # Should sleep 3, 7, 7, 7 (capped at max_wait=7)
            mock_sleep.assert_has_calls(
                [
                    call(3),
                    call(7),
                    call(7),
                    call(7),
                ]
            )

    class TestAsync:
        async def test_retry_decorator_success(self):
            @retry(until=AttemptsExhausted(2))
            async def f(x: int) -> int:
                return x + 1

            assert await f(2) == 3

        async def test_retry_decorator_eventual_success(self):
            attempts = 0

            @retry(until=AttemptsExhausted(3))
            async def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise Exception("fail")
                return x

            assert await f(7) == 7
            assert attempts == 2

        async def test_retry_decorator_no_until(self):
            @retry
            async def f(x: int) -> int:
                return x * 3

            assert await f(3) == 9

        async def test_retry_with_invalid_stop_condition(self):
            class NeverAttempt(StopCondition):
                def is_met(self, context: AttemptState | None) -> bool:  # noqa: ARG002
                    return True

            @retry(until=NeverAttempt())
            async def f(x: int) -> int:
                return x * 3

            with pytest.raises(
                RuntimeError,
                match="Failed to make a single attempt with the given stop condition",
            ):
                await f(3)

        @pytest.mark.parametrize("wait", [5, datetime.timedelta(minutes=5), 5.0])
        async def test_retry_decorator_with_wait(
            self, wait: int | float | datetime.timedelta, mock_async_sleep: AsyncMock
        ):
            attempts = 0

            @retry(until=AttemptsExhausted(3), wait=wait)
            async def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise Exception("fail")
                return x * 3

            assert await f(3) == 9

            if isinstance(wait, datetime.timedelta):
                mock_async_sleep.assert_called_once_with(wait.total_seconds())
            else:
                mock_async_sleep.assert_called_once_with(wait)

        async def test_retry_decorator_with_exponential_backoff_callable(
            self, mock_async_sleep: AsyncMock
        ):
            attempts = 0

            def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
                return 2 ** (next.attempt - 1)

            @retry(until=AttemptsExhausted(4), wait=exp_backoff)
            async def f(x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise Exception("fail")
                return x

            assert await f(5) == 5
            # Should sleep 2, 4, 8 seconds (for attempts 2, 3, 4)
            mock_async_sleep.assert_has_calls(
                [
                    call(2),
                    call(4),
                    call(8),
                ]
            )

        async def test_retry_decorator_with_exponential_backoff_callable_and_max_wait(
            self, mock_async_sleep: AsyncMock
        ):
            attempts = 0

            def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
                return min(3 ** (next.attempt - 1), 7)

            @retry(until=AttemptsExhausted(5), wait=exp_backoff)
            async def f(_x: int) -> int:
                nonlocal attempts
                attempts += 1
                if attempts < 5:
                    raise Exception("fail")
                return _x

            assert await f(10) == 10
            # Should sleep 3, 7, 7, 7 (capped at max_wait=7)
            mock_async_sleep.assert_has_calls(
                [
                    call(3),
                    call(7),
                    call(7),
                    call(7),
                ]
            )


class TestHookDecorators:
    class TestSync:
        def test_retry_decorator_with_before_attempt_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()

            @retry(until=AttemptsExhausted(2))
            def f(x: int) -> int:
                return x * 3

            @f.before_attempt
            def before_attempt(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.before_attempt
            async def async_before_attempt(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            f(3)
            spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, phase=Phase.PENDING)
            )
            async_spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, phase=Phase.PENDING)
            )

        def test_retry_decorator_with_on_success_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()

            @retry(until=AttemptsExhausted(2))
            def f(x: int) -> int:
                return x * 3

            @f.on_success
            def on_success(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.on_success
            async def async_on_success(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            f(3)
            spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, result=9, phase=Phase.SUCCEEDED)
            )
            async_spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, result=9, phase=Phase.SUCCEEDED)
            )

        def test_retry_decorator_with_on_failure_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2))
            def f(_x: int) -> int:
                raise exception

            @f.on_failure
            def on_failure(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.on_failure
            async def async_on_failure(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(attempt=1, exception=exception, phase=Phase.FAILED)
                    ),
                    call(
                        AttemptState(attempt=2, exception=exception, phase=Phase.FAILED)
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(attempt=1, exception=exception, phase=Phase.FAILED)
                    ),
                    call(
                        AttemptState(attempt=2, exception=exception, phase=Phase.FAILED)
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_retry_decorator_with_before_wait_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2), wait=1)
            def f(_x: int) -> int:
                raise exception

            @f.before_wait
            def before_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.before_wait
            async def async_before_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_retry_decorator_with_after_wait_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2), wait=1)
            def f(_x: int) -> int:
                raise exception

            @f.after_wait
            def after_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.after_wait
            async def async_after_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )

    class TestAsync:
        async def test_retry_decorator_with_before_attempt_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()

            @retry(until=AttemptsExhausted(2))
            async def f(x: int) -> int:
                return x * 3

            @f.before_attempt
            def before_attempt(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.before_attempt
            async def async_before_attempt(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            await f(3)
            spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, phase=Phase.PENDING)
            )
            async_spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, phase=Phase.PENDING)
            )

        async def test_retry_decorator_with_on_success_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()

            @retry(until=AttemptsExhausted(2))
            async def f(x: int) -> int:
                return x * 3

            @f.on_success
            def on_success(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.on_success
            async def async_on_success(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            await f(3)
            spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, result=9, phase=Phase.SUCCEEDED)
            )
            async_spy.assert_called_once_with(
                AttemptState(attempt=1, exception=None, result=9, phase=Phase.SUCCEEDED)
            )

        async def test_retry_decorator_with_on_failure_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2))
            async def f(_x: int) -> int:
                raise exception

            @f.on_failure
            def on_failure(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.on_failure
            async def async_on_failure(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                await f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(attempt=1, exception=exception, phase=Phase.FAILED)
                    ),
                    call(
                        AttemptState(attempt=2, exception=exception, phase=Phase.FAILED)
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(attempt=1, exception=exception, phase=Phase.FAILED)
                    ),
                    call(
                        AttemptState(attempt=2, exception=exception, phase=Phase.FAILED)
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_retry_decorator_with_before_wait_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2), wait=1)
            async def f(_x: int) -> int:
                raise exception

            @f.before_wait
            def before_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.before_wait
            async def async_before_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                await f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_retry_decorator_with_after_wait_hook(self):
            spy = MagicMock()
            async_spy = AsyncMock()
            exception = RuntimeError()

            @retry(until=AttemptsExhausted(2), wait=1)
            async def f(_x: int) -> int:
                raise exception

            @f.after_wait
            def after_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                spy(state)

            @f.after_wait
            async def async_after_wait(state: AttemptState):  # pyright: ignore[reportUnusedFunction]
                await async_spy(state)

            with pytest.raises(RuntimeError):
                await f(3)

            spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )
