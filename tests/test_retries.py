from unittest.mock import AsyncMock, MagicMock, call

import pytest

from prefect.retries import AsyncRetryBlock, RetryBlock, exponential_backoff, retry


@pytest.fixture
def mock_sleep(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock()
    monkeypatch.setattr("time.sleep", mock)
    return mock


@pytest.fixture
def mock_async_sleep(monkeypatch: pytest.MonkeyPatch):
    mock = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", mock)
    return mock


class TestSync:
    class TestBasicRetry:
        def test_successful_retry(self):
            attempts = 0

            @retry(attempts=3)
            def failing_function():
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise ValueError("Temporary failure")
                return "success"

            result = failing_function()
            assert result == "success"
            assert attempts == 2

        def test_max_attempts_exceeded(self):
            attempts = 0

            @retry(attempts=3)
            def always_failing_function():
                nonlocal attempts
                attempts += 1
                raise ValueError("Permanent failure")

            with pytest.raises(ValueError, match="Permanent failure"):
                always_failing_function()

            assert attempts == 3

        def test_no_retry_on_success(self):
            attempts = 0

            @retry(attempts=3)
            def successful_function():
                nonlocal attempts
                attempts += 1
                return "success"

            result = successful_function()
            assert result == "success"
            assert attempts == 1

    class TestWait:
        def test_fixed_wait_time(self, mock_sleep: MagicMock):
            attempts = 0

            @retry(attempts=3, wait=1.0)
            def function_with_wait():
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_wait()
            assert attempts == 3
            assert mock_sleep.call_args_list == [
                call(1.0),
                call(1.0),
            ]

        def test_wait_sequence(self, mock_sleep: MagicMock):
            attempts = 0

            @retry(attempts=4, wait=[1.0, 2.0, 3.0])
            def function_with_wait_sequence():
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_wait_sequence()
            assert attempts == 4
            assert mock_sleep.call_args_list == [call(1.0), call(2.0), call(3.0)]

        def test_short_wait_sequence(self, mock_sleep: MagicMock):
            attempts = 0

            @retry(attempts=4, wait=[1.0, 2.0])
            def function_with_short_wait_sequence():
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_short_wait_sequence()
            assert attempts == 4
            assert mock_sleep.call_args_list == [call(1.0), call(2.0), call(2.0)]

        def test_wait_callback(self, mock_sleep: MagicMock):
            attempts = 0

            def wait_callback(attempt: int) -> float:
                return float(attempt)

            @retry(attempts=3, wait=wait_callback)
            def function_with_wait_callback():
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_wait_callback()
            assert attempts == 3
            assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    class TestCallbacks:
        def test_before_attempt_callback(self):
            attempts: list[int] = []

            def before_attempt(attempt: int, max_attempts: int) -> None:
                attempts.append(attempt)

            @retry(attempts=3, before_attempt=before_attempt)
            def failing_function():
                raise ValueError("Failure")

            with pytest.raises(ValueError):
                failing_function()
            assert attempts == [0, 1, 2]

        def test_after_failure_callback(self):
            failures: list[tuple[int, str]] = []

            def after_failure(
                e: Exception, attempt: int, max_attempts: int, wait_time: float
            ) -> None:
                failures.append((attempt, str(e)))

            @retry(attempts=3, on_failure=after_failure)
            def failing_function():
                raise ValueError("Test failure")

            with pytest.raises(ValueError):
                failing_function()
            assert len(failures) == 3
            assert all(attempt == i for i, (attempt, _) in enumerate(failures))
            assert all("Test failure" in msg for _, msg in failures)

    class TestRetryBlock:
        def test_retriable_block_success(self):
            attempts = 0

            for attempt in RetryBlock(attempts=3):
                with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise ValueError(f"Temporary failure {attempts}")

            assert attempts == 2

        def test_retriable_block_failure(self):
            attempts = 0

            with pytest.raises(ValueError):
                for attempt in RetryBlock(attempts=3):
                    with attempt:
                        attempts += 1
                        raise ValueError("Permanent failure")

            assert attempts == 3

        def test_retriable_block_with_generator(self):
            attempts = 0

            def generator():
                yield 1
                yield 2
                raise ValueError("Permanent failure")

            with pytest.raises(ValueError):
                for attempt in RetryBlock(attempts=3):
                    with attempt:
                        attempts += 1
                        for _ in generator():
                            pass

            assert attempts == 3

    class TestShouldRetry:
        def test_retry_with_custom_should_retry(self):
            attempts = 0

            def should_retry(e: Exception) -> bool:
                return isinstance(e, RuntimeError)

            @retry(attempts=3, should_retry=should_retry)
            def function_with_custom_retry():
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise RuntimeError("retry this")
                raise ValueError("don't retry this")

            with pytest.raises(ValueError, match="don't retry this"):
                function_with_custom_retry()
            assert attempts == 2

        def test_retry_with_boolean_should_retry(self):
            attempts = 0

            @retry(attempts=3, should_retry=False)
            def function_with_no_retry():
                nonlocal attempts
                attempts += 1
                raise ValueError("This should not be retried")

            with pytest.raises(ValueError):
                function_with_no_retry()
            assert attempts == 1


class TestAsync:
    class TestBasicRetry:
        async def test_successful_retry(self):
            attempts = 0

            @retry(attempts=3)
            async def failing_async_function():
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise ValueError("Temporary failure")
                return "success"

            result = await failing_async_function()
            assert result == "success"
            assert attempts == 2

        async def test_max_attempts_exceeded(self):
            attempts = 0

            @retry(attempts=3)
            async def always_failing_async_function():
                nonlocal attempts
                attempts += 1
                raise ValueError("Permanent failure")

            with pytest.raises(ValueError, match="Permanent failure"):
                await always_failing_async_function()
            assert attempts == 3

        async def test_no_retry_on_success(self):
            attempts = 0

            @retry(attempts=3)
            async def successful_async_function():
                nonlocal attempts
                attempts += 1
                return "success"

            result = await successful_async_function()
            assert result == "success"
            assert attempts == 1

    class TestWait:
        async def test_fixed_wait_time(self, mock_async_sleep: MagicMock):
            attempts = 0

            @retry(attempts=3, wait=1.0)
            async def function_with_wait():
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise ValueError("Temporary failure")
                return "success"

            await function_with_wait()
            assert attempts == 3
            assert mock_async_sleep.call_args_list == [
                call(1.0),
                call(1.0),
            ]

        def test_wait_sequence(self, mock_sleep: MagicMock):
            attempts = 0

            @retry(attempts=4, wait=[1.0, 2.0, 3.0])
            def function_with_wait_sequence():
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_wait_sequence()
            assert attempts == 4
            assert mock_sleep.call_args_list == [call(1.0), call(2.0), call(3.0)]

        def test_short_wait_sequence(self, mock_sleep: MagicMock):
            attempts = 0

            @retry(attempts=4, wait=[1.0, 2.0])
            def function_with_short_wait_sequence():
                nonlocal attempts
                attempts += 1
                if attempts < 4:
                    raise ValueError("Temporary failure")
                return "success"

            function_with_short_wait_sequence()
            assert attempts == 4
            assert mock_sleep.call_args_list == [call(1.0), call(2.0), call(2.0)]

        async def test_wait_callback(self, mock_async_sleep: MagicMock):
            attempts = 0

            def wait_callback(attempt: int) -> float:
                return float(attempt)

            @retry(attempts=3, wait=wait_callback)
            async def function_with_wait_callback():
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise ValueError("Temporary failure")
                return "success"

            await function_with_wait_callback()
            assert attempts == 3
            assert mock_async_sleep.call_args_list == [call(1.0), call(2.0)]

    class TestCallbacks:
        async def test_before_attempt_callback(self):
            attempts: list[int] = []

            def before_attempt(attempt: int, max_attempts: int) -> None:
                attempts.append(attempt)

            @retry(attempts=3, before_attempt=before_attempt)
            async def failing_function():
                raise ValueError("Failure")

            with pytest.raises(ValueError):
                await failing_function()
            assert attempts == [0, 1, 2]

        async def test_after_failure_callback(self):
            failures: list[tuple[int, str]] = []

            def after_failure(
                e: Exception, attempt: int, max_attempts: int, wait_time: float
            ) -> None:
                failures.append((attempt, str(e)))

            @retry(attempts=3, on_failure=after_failure)
            async def failing_function():
                raise ValueError("Test failure")

            with pytest.raises(ValueError):
                await failing_function()
            assert len(failures) == 3
            assert all(attempt == i for i, (attempt, _) in enumerate(failures))
            assert all("Test failure" in msg for _, msg in failures)

    class TestRetryBlock:
        async def test_retriable_block_success(self):
            attempts = 0

            async for attempt in AsyncRetryBlock(attempts=3):
                async with attempt:
                    attempts += 1
                    if attempts < 2:
                        raise ValueError(f"Temporary failure {attempts}")

            assert attempts == 2

        async def test_retriable_block_failure(self):
            attempts = 0

            with pytest.raises(ValueError):
                async for attempt in AsyncRetryBlock(attempts=3):
                    async with attempt:
                        attempts += 1
                        raise ValueError("Permanent failure")

            assert attempts == 3

        async def test_retriable_block_with_generator(self):
            attempts = 0

            async def generator():
                yield 1
                yield 2
                raise ValueError("Permanent failure")

            with pytest.raises(ValueError):
                async for attempt in AsyncRetryBlock(attempts=3):
                    async with attempt:
                        attempts += 1
                        async for _ in generator():
                            pass

            assert attempts == 3

    class TestShouldRetry:
        async def test_retry_with_custom_should_retry(self):
            attempts = 0

            def should_retry(e: Exception) -> bool:
                return isinstance(e, RuntimeError)

            @retry(attempts=3, should_retry=should_retry)
            async def function_with_custom_retry():
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    raise RuntimeError("retry this")
                raise ValueError("don't retry this")

            with pytest.raises(ValueError, match="don't retry this"):
                await function_with_custom_retry()
            assert attempts == 2

        async def test_retry_with_boolean_should_retry(self):
            attempts = 0

            @retry(attempts=3, should_retry=False)
            async def function_with_no_retry():
                nonlocal attempts
                attempts += 1
                raise ValueError("This should not be retried")

            with pytest.raises(ValueError):
                await function_with_no_retry()
            assert attempts == 1

    class TestExponentialBackoff:
        def test_without_jitter(self):
            waiter = exponential_backoff(base=1.0, max_wait=10.0, jitter=0.0)
            assert waiter(0) == 1.0
            assert waiter(1) == 2.0
            assert waiter(2) == 4.0
            assert waiter(3) == 8.0
            assert waiter(4) == 10.0
            assert waiter(5) == 10.0

        def test_with_jitter(self):
            waiter = exponential_backoff(base=1.0, max_wait=10.0, jitter=0.5)
            assert waiter(0) == pytest.approx(1.0, 0.5)
            assert waiter(1) == pytest.approx(2.0, 1.0)
            assert waiter(2) == pytest.approx(4.0, 2.0)
            assert waiter(3) == pytest.approx(8.0, 4.0)
            assert waiter(4) == pytest.approx(10.0, 5.0)
            assert waiter(5) == pytest.approx(10.0, 5.0)
