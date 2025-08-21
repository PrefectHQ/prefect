from __future__ import annotations

import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from prefect.retries import attempting, attempting_async
from prefect.retries._attempts import (
    AsyncAttemptGenerator,
    AttemptGenerator,
)
from prefect.retries._dataclasses import AttemptState, Phase
from prefect.retries.stop_conditions import AttemptsExhausted, NoException


class TestAttemptGenerator:
    def test_default_stop_condition(self):
        generator = AttemptGenerator()
        assert generator.stop_condition == NoException()


class TestAsyncAttemptGenerator:
    def test_default_stop_condition(self):
        generator = AsyncAttemptGenerator()
        assert generator.stop_condition == NoException()


class TestAttempting:
    def test_retry_context_with_eventual_success(self):
        attempts = 0
        result = None
        for attempt in attempting(until=AttemptsExhausted(3)):
            with attempt:
                attempts += 1
                if attempts < 2:
                    raise Exception("Test exception")
                result = "Success"

        assert result is not None
        assert attempts == 2

    def test_retry_context_with_failure(self):
        attempts = 0
        with pytest.raises(RuntimeError):
            for attempt in attempting(until=AttemptsExhausted(3)):
                with attempt:
                    attempts += 1
                    raise RuntimeError("Test exception")

        assert attempts == 3


class TestAsyncAttempting:
    async def test_retry_context_with_eventual_success(self):
        attempts = 0
        result = None
        async for attempt in attempting_async(until=AttemptsExhausted(3)):
            async with attempt:
                attempts += 1
                if attempts < 2:
                    raise Exception("Test exception")
                result = "Success"

        assert result is not None
        assert attempts == 2

    async def test_retry_context_with_failure(self):
        attempts = 0
        with pytest.raises(RuntimeError):
            async for attempt in attempting_async(until=AttemptsExhausted(3)):
                async with attempt:
                    attempts += 1
                    raise RuntimeError("Test exception")

        assert attempts == 3


class TestWait:
    @pytest.mark.parametrize("wait", [5, datetime.timedelta(minutes=5), 5.0])
    def test_wait(self, wait: int | float | datetime.timedelta, mock_sleep: MagicMock):
        attempts = 0
        for attempt in attempting(until=AttemptsExhausted(3), wait=wait):
            with attempt:
                attempts += 1
                if attempts < 2:
                    raise Exception("Test exception")

        if isinstance(wait, datetime.timedelta):
            mock_sleep.assert_called_once_with(wait.total_seconds())
        else:
            mock_sleep.assert_called_once_with(wait)

    def test_wait_with_exponential_backoff_callable(self, mock_sleep: MagicMock):
        attempts = 0

        def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
            return 2 ** (next.attempt - 1)

        for attempt in attempting(until=AttemptsExhausted(4), wait=exp_backoff):
            with attempt:
                attempts += 1

                if attempts < 4:
                    raise Exception("fail")

        assert attempts == 4
        mock_sleep.assert_has_calls(
            [
                call(2.0),
                call(4.0),
                call(8.0),
            ]
        )


class TestAsyncWait:
    @pytest.mark.parametrize("wait", [5, datetime.timedelta(minutes=5), 5.0])
    async def test_wait(
        self, wait: int | float | datetime.timedelta, mock_async_sleep: AsyncMock
    ):
        attempts = 0
        async for attempt in attempting_async(until=AttemptsExhausted(3), wait=wait):
            async with attempt:
                attempts += 1
                if attempts < 2:
                    raise Exception("Test exception")

        if isinstance(wait, datetime.timedelta):
            mock_async_sleep.assert_awaited_once_with(wait.total_seconds())
        else:
            mock_async_sleep.assert_awaited_once_with(wait)

    async def test_wait_with_exponential_backoff_callable(
        self, mock_async_sleep: AsyncMock
    ):
        attempts = 0

        def exp_backoff(prev: AttemptState | None, next: AttemptState) -> int:  # noqa: ARG001
            return 2 ** (next.attempt - 1)

        async for attempt in attempting_async(
            until=AttemptsExhausted(4), wait=exp_backoff
        ):
            async with attempt:
                attempts += 1

                if attempts < 4:
                    raise Exception("fail")

        assert attempts == 4
        mock_async_sleep.assert_has_calls(
            [
                call(2.0),
                call(4.0),
                call(8.0),
            ]
        )


class TestAttemptingHooks:
    class TestSync:
        def test_before_attempt(self):
            attempts = 0
            spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            for attempt in attempting(
                until=AttemptsExhausted(3), before_attempt=[spy, async_hook_wrapper]
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=None, phase=Phase.PENDING
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=None, phase=Phase.PENDING
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_on_success(self):
            attempts = 0
            spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            for attempt in attempting(
                until=AttemptsExhausted(3),
                on_success=[spy, async_hook_wrapper],
                wait=1,
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            spy.assert_called_once_with(
                state=AttemptState(attempt=2, exception=None, phase=Phase.SUCCEEDED)
            )
            async_spy.assert_called_once_with(
                state=AttemptState(attempt=2, exception=None, phase=Phase.SUCCEEDED)
            )

        def test_on_failure(self):
            attempts = 0
            spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            exception = RuntimeError("Test exception")
            with pytest.raises(RuntimeError):
                for attempt in attempting(
                    until=AttemptsExhausted(3), on_failure=[spy, async_hook_wrapper]
                ):
                    with attempt:
                        attempts += 1
                        raise exception

            assert attempts == 3
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=3, exception=exception, phase=Phase.FAILED
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=3, exception=exception, phase=Phase.FAILED
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_before_wait(self):
            attempts = 0
            spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            for attempt in attempting(
                until=AttemptsExhausted(3),
                wait=1,
                before_wait=[spy, async_hook_wrapper],
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
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
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_after_wait(self):
            attempts = 0
            spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            for attempt in attempting(
                until=AttemptsExhausted(3), wait=1, after_wait=[spy, async_hook_wrapper]
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
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
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_all_hooks_are_called(self):
            attempts = 0
            spy = MagicMock()
            exception = Exception("Test exception")

            for attempt in attempting(
                until=AttemptsExhausted(3),
                wait=1,
                before_attempt=[spy],
                on_success=[spy],
                on_failure=[spy],
                before_wait=[spy],
                after_wait=[spy],
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise exception

            assert attempts == 2
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.WAITING,
                            wait_seconds=1,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.PENDING,
                            wait_seconds=None,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.PENDING,
                            wait_seconds=None,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.SUCCEEDED,
                            wait_seconds=None,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_sleep")
        def test_hook_failure_does_not_stop_execution(
            self, caplog: pytest.LogCaptureFixture
        ):
            def failing_hook(state: AttemptState | None):  # noqa: ARG001
                raise Exception("Test exception")

            async def async_failing_hook(state: AttemptState) -> None:  # noqa: ARG001
                raise Exception("Test exception")

            attempts = 0

            for attempt in attempting(
                until=AttemptsExhausted(3),
                wait=1,
                before_attempt=[failing_hook, async_failing_hook],
                on_success=[failing_hook, async_failing_hook],
                on_failure=[failing_hook, async_failing_hook],
                after_wait=[failing_hook, async_failing_hook],
                before_wait=[failing_hook, async_failing_hook],
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            assert "Error calling before_wait hook failing_hook" in caplog.text
            assert "Error calling after_wait hook failing_hook" in caplog.text
            assert "Error calling on_failure hook failing_hook" in caplog.text
            assert "Error calling on_success hook failing_hook" in caplog.text
            assert "Error calling before_attempt hook failing_hook" in caplog.text
            assert "Error calling before_wait hook async_failing_hook" in caplog.text
            assert "Error calling after_wait hook async_failing_hook" in caplog.text
            assert "Error calling on_failure hook async_failing_hook" in caplog.text
            assert "Error calling on_success hook async_failing_hook" in caplog.text
            assert "Error calling before_attempt hook async_failing_hook" in caplog.text

        def test_async_hooks_work_with_no_current_loop(self):
            # Clear the current event loop so that asyncio.get_event_loop() raises a
            # RuntimeError
            asyncio.set_event_loop(None)

            attempts = 0
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            for attempt in attempting(
                until=AttemptsExhausted(3), before_attempt=[async_hook_wrapper]
            ):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            async_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=None, phase=Phase.PENDING
                        )
                    ),
                ]
            )

    class TestAsync:
        async def test_before_attempt(self):
            attempts = 0
            sync_spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                before_attempt=[sync_spy, async_hook_wrapper],
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            sync_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=None, phase=Phase.PENDING
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=None, phase=Phase.PENDING
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_on_success(self):
            attempts = 0
            sync_spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                on_success=[sync_spy, async_hook_wrapper],
                wait=1,
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            sync_spy.assert_called_once_with(
                state=AttemptState(attempt=2, exception=None, phase=Phase.SUCCEEDED)
            )
            async_spy.assert_called_once_with(
                state=AttemptState(attempt=2, exception=None, phase=Phase.SUCCEEDED)
            )

        async def test_on_failure(self):
            attempts = 0
            sync_spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            exception = RuntimeError("Test exception")
            with pytest.raises(RuntimeError):
                async for attempt in attempting_async(
                    until=AttemptsExhausted(3),
                    on_failure=[sync_spy, async_hook_wrapper],
                ):
                    async with attempt:
                        attempts += 1
                        raise exception

            assert attempts == 3
            sync_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=3, exception=exception, phase=Phase.FAILED
                        )
                    ),
                ]
            )
            async_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=3, exception=exception, phase=Phase.FAILED
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_before_wait(self):
            attempts = 0
            sync_spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                wait=1,
                before_wait=[sync_spy, async_hook_wrapper],
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            sync_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
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
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=1,
                            phase=Phase.WAITING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_after_wait(self):
            attempts = 0
            sync_spy = MagicMock()
            async_spy = AsyncMock()

            async def async_hook_wrapper(state: AttemptState) -> None:
                await async_spy(state=state)

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                wait=1,
                after_wait=[sync_spy, async_hook_wrapper],
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            sync_spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
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
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            wait_seconds=None,
                            phase=Phase.PENDING,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_all_hooks_are_called(self):
            attempts = 0
            spy = AsyncMock()
            exception = Exception("Test exception")

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                wait=1,
                before_attempt=[spy],
                on_success=[spy],
                on_failure=[spy],
                before_wait=[spy],
                after_wait=[spy],
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise exception

            assert attempts == 2
            spy.assert_has_calls(
                [
                    call(
                        state=AttemptState(
                            attempt=1, exception=None, phase=Phase.PENDING
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=1, exception=exception, phase=Phase.FAILED
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.WAITING,
                            wait_seconds=1,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.PENDING,
                            wait_seconds=None,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.PENDING,
                            wait_seconds=None,
                        )
                    ),
                    call(
                        state=AttemptState(
                            attempt=2,
                            exception=None,
                            phase=Phase.SUCCEEDED,
                            wait_seconds=None,
                        )
                    ),
                ]
            )

        @pytest.mark.usefixtures("mock_async_sleep")
        async def test_hook_failure_does_not_stop_execution(
            self, caplog: pytest.LogCaptureFixture
        ):
            def sync_failing_hook(state: AttemptState | None):  # noqa: ARG001
                raise Exception("Test exception")

            async def async_failing_hook(state: AttemptState | None):  # noqa: ARG001
                raise Exception("Test exception")

            attempts = 0

            async for attempt in attempting_async(
                until=AttemptsExhausted(3),
                wait=1,
                before_attempt=[sync_failing_hook, async_failing_hook],
                on_success=[sync_failing_hook, async_failing_hook],
                on_failure=[sync_failing_hook, async_failing_hook],
                after_wait=[sync_failing_hook, async_failing_hook],
                before_wait=[sync_failing_hook, async_failing_hook],
            ):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise Exception("Test exception")

            assert attempts == 2
            assert "Error calling before_wait hook sync_failing_hook" in caplog.text
            assert "Error calling after_wait hook sync_failing_hook" in caplog.text
            assert "Error calling on_failure hook sync_failing_hook" in caplog.text
            assert "Error calling on_success hook sync_failing_hook" in caplog.text
            assert "Error calling before_attempt hook sync_failing_hook" in caplog.text
            assert "Error calling before_wait hook async_failing_hook" in caplog.text
            assert "Error calling after_wait hook async_failing_hook" in caplog.text
            assert "Error calling on_failure hook async_failing_hook" in caplog.text
            assert "Error calling on_success hook async_failing_hook" in caplog.text
            assert "Error calling before_attempt hook async_failing_hook" in caplog.text
