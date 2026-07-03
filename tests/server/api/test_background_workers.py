"""Tests for background worker supervision logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from prefect.server.api.background_workers import (
    _is_task_cancelling,
    _supervised_worker,
)


class TestSupervisedWorker:
    """Tests for the _supervised_worker restart loop."""

    async def test_clean_exit_does_not_restart(self):
        """When run_forever() returns cleanly, _supervised_worker exits."""
        worker = MagicMock()
        worker.run_forever = AsyncMock(return_value=None)

        await _supervised_worker(worker)

        worker.run_forever.assert_awaited_once()

    async def test_restarts_on_redis_timeout_error(self):
        """run_forever() dying from TimeoutError triggers a restart."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 0
        # First call raises TimeoutError, second call succeeds
        worker.run_forever = AsyncMock(
            side_effect=[RedisTimeoutError("Timeout connecting to server"), None]
        )

        with patch("prefect.server.api.background_workers.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await _supervised_worker(worker)

        assert worker.run_forever.await_count == 2
        mock_sleep.assert_awaited_once_with(0)

    async def test_restarts_on_generic_exception(self):
        """run_forever() dying from any Exception triggers a restart."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 0
        worker.run_forever = AsyncMock(side_effect=[RuntimeError("unexpected"), None])

        with patch("prefect.server.api.background_workers.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await _supervised_worker(worker)

        assert worker.run_forever.await_count == 2

    async def test_cancelled_error_propagates(self):
        """CancelledError is not caught — it propagates to stop the supervisor."""
        worker = MagicMock()
        worker.run_forever = AsyncMock(side_effect=asyncio.CancelledError())

        with pytest.raises(asyncio.CancelledError):
            await _supervised_worker(worker)

        worker.run_forever.assert_awaited_once()

    async def test_uses_reconnection_delay(self):
        """The sleep between restarts uses worker.reconnection_delay."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 7.5
        worker.run_forever = AsyncMock(side_effect=[RedisTimeoutError("timeout"), None])

        with patch("prefect.server.api.background_workers.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await _supervised_worker(worker)

        mock_sleep.assert_awaited_once_with(7.5)

    async def test_restarts_multiple_times(self):
        """The supervisor keeps restarting across multiple failures."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 0
        worker.run_forever = AsyncMock(
            side_effect=[
                RedisTimeoutError("timeout 1"),
                ConnectionError("connection lost"),
                RuntimeError("something else"),
                None,  # finally succeeds
            ]
        )

        with patch("prefect.server.api.background_workers.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await _supervised_worker(worker)

        assert worker.run_forever.await_count == 4
        assert mock_sleep.await_count == 3

    async def test_logs_error_on_restart(self):
        """Each restart logs an error with the exception details."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 0
        worker.run_forever = AsyncMock(
            side_effect=[RedisTimeoutError("Timeout connecting to server"), None]
        )

        with (
            patch(
                "prefect.server.api.background_workers.asyncio.sleep",
                return_value=None,
            ),
            patch("prefect.server.api.background_workers.logger") as mock_logger,
        ):
            await _supervised_worker(worker)

        mock_logger.error.assert_called_once()
        args = mock_logger.error.call_args
        assert "Docket worker exited unexpectedly" in args[0][0]
        assert args[1]["exc_info"] is True

    async def test_propagates_cancellation_when_task_is_cancelling(self):
        """If the task is being cancelled but run_forever() raises a non-CancelledError
        (e.g. during Docket cleanup), the supervisor re-raises CancelledError instead
        of restarting."""
        worker = MagicMock()
        worker.reconnection_delay.total_seconds.return_value = 0
        worker.run_forever = AsyncMock(
            side_effect=RedisTimeoutError("cleanup error during shutdown")
        )

        with patch(
            "prefect.server.api.background_workers._is_task_cancelling",
            return_value=True,
        ):
            with pytest.raises(asyncio.CancelledError):
                await _supervised_worker(worker)

        worker.run_forever.assert_awaited_once()


class TestIsTaskCancelling:
    """Tests for the _is_task_cancelling helper."""

    async def test_returns_false_normally(self):
        assert _is_task_cancelling() is False
