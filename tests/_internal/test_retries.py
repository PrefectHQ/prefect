from unittest.mock import AsyncMock, Mock, patch

import pytest

from prefect._internal.retries import retry_async_fn


@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock:
        yield mock


class TestRetryAsyncFn:
    async def test_successful_execution(self):
        @retry_async_fn()
        async def success_func():
            return "Success"

        result = await success_func()
        assert result == "Success"

    async def test_max_attempts(self, mock_sleep):
        mock_func = AsyncMock(side_effect=ValueError("Test error"))

        @retry_async_fn(max_attempts=3)
        async def fail_func():
            await mock_func()

        with pytest.raises(ValueError, match="Test error"):
            await fail_func()

        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    async def test_custom_backoff_strategy(self, mock_sleep):
        custom_strategy = Mock(return_value=0.1)

        @retry_async_fn(max_attempts=3, backoff_strategy=custom_strategy)
        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await fail_func()

        assert custom_strategy.call_count == 2  # Called for the 2nd and 3rd attempts
        assert mock_sleep.call_count == 2
        assert all(call.args[0] == 0.1 for call in mock_sleep.call_args_list)

    async def test_specific_exception_retry(self, mock_sleep):
        @retry_async_fn(max_attempts=3, retry_on_exceptions=(ValueError,))
        async def mixed_fail_func():
            if mixed_fail_func.calls == 0:
                mixed_fail_func.calls += 1
                raise ValueError("Retry this")
            elif mixed_fail_func.calls == 1:
                mixed_fail_func.calls += 1
                raise TypeError("Don't retry this")
            return "Success"

        mixed_fail_func.calls = 0

        with pytest.raises(TypeError, match="Don't retry this"):
            await mixed_fail_func()

        assert mixed_fail_func.calls == 2
        assert mock_sleep.call_count == 1

    async def test_logging(self, caplog, mock_sleep):
        @retry_async_fn(max_attempts=2)
        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"), caplog.at_level("WARNING"):
            await fail_func()

        assert all(
            substr in caplog.text
            for substr in ["Attempt 1 of function", "Test error", "Retrying in"]
        )
        assert "'fail_func' failed after 2 attempts" in caplog.text
        assert mock_sleep.call_count == 1

    async def test_exponential_backoff_with_jitter(self, mock_sleep):
        @retry_async_fn(max_attempts=4, base_delay=1, max_delay=10)
        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await fail_func()

        assert mock_sleep.call_count == 3
        delays = [call.args[0] for call in mock_sleep.call_args_list]

        # Check that delays are within expected ranges
        assert 0.7 <= delays[0] <= 1.3  # 1 * 1.3
        assert 1.4 <= delays[1] <= 2.6  # 2 * 1.3
        assert 2.8 <= delays[2] <= 5.2  # 4 * 1.3

    async def test_retry_successful_after_failures(self, mock_sleep):
        mock_func = AsyncMock(
            side_effect=[ValueError("Error 1"), ValueError("Error 2"), "Success"]
        )

        @retry_async_fn(max_attempts=4)
        async def eventual_success_func():
            return await mock_func()

        result = await eventual_success_func()
        assert result == "Success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    async def test_should_not_retry_short_circuits(self, mock_sleep):
        """When should_not_retry returns True, raises immediately without retrying."""
        mock_func = AsyncMock(side_effect=ValueError("no retry"))

        @retry_async_fn(max_attempts=3, should_not_retry=lambda e: True)
        async def fail_func():
            await mock_func()

        with pytest.raises(ValueError, match="no retry"):
            await fail_func()

        assert mock_func.call_count == 1
        assert mock_sleep.call_count == 0

    async def test_should_not_retry_false_does_not_affect_retries(self, mock_sleep):
        """When should_not_retry returns False, normal retry behavior is preserved."""
        mock_func = AsyncMock(side_effect=ValueError("retry me"))

        @retry_async_fn(max_attempts=3, should_not_retry=lambda e: False)
        async def fail_func():
            await mock_func()

        with pytest.raises(ValueError, match="retry me"):
            await fail_func()

        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    async def test_should_not_retry_only_short_circuits_matching_exceptions(
        self, mock_sleep
    ):
        """should_not_retry inspects the exception — only short-circuits when it returns True."""
        mock_func = AsyncMock(
            side_effect=[ValueError("retry this"), ValueError("stop here")]
        )

        @retry_async_fn(
            max_attempts=5,
            should_not_retry=lambda e: "stop" in str(e),
        )
        async def mixed_func():
            await mock_func()

        with pytest.raises(ValueError, match="stop here"):
            await mixed_func()

        assert mock_func.call_count == 2  # retried once, then short-circuited
        assert mock_sleep.call_count == 1
