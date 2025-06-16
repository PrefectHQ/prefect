from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from prefect.server.logs.messaging import (
    create_log_publisher,
    publish_log,
    publish_logs,
)
from prefect.server.schemas.core import Log
from prefect.settings import (
    PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED,
    temporary_settings,
)
from prefect.types._datetime import now


@pytest.fixture
def sample_log():
    """A sample log record"""
    return Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Test message",
        timestamp=now("UTC"),
        flow_run_id=uuid4(),
        task_run_id=uuid4(),
    )


@pytest.fixture
def sample_logs(sample_log):
    """Multiple sample log records"""
    log2 = Log(
        id=uuid4(),
        name="test.logger2",
        level=40,
        message="Test message 2",
        timestamp=now("UTC"),
        flow_run_id=uuid4(),
        task_run_id=None,
    )
    return [sample_log, log2]


@pytest.mark.asyncio
async def test_create_log_publisher():
    """Test creating a log publisher"""
    with patch(
        "prefect.server.logs.messaging.messaging.create_publisher"
    ) as mock_create:
        mock_publisher = AsyncMock()
        mock_create.return_value.__aenter__.return_value = mock_publisher

        async with create_log_publisher() as publisher:
            assert publisher == mock_publisher

        mock_create.assert_called_once_with(topic="logs")


@pytest.mark.asyncio
async def test_publish_log_when_disabled(sample_log):
    """Test that publish_log does nothing when streaming is disabled"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: False}):
        # Should return early without doing anything
        await publish_log(sample_log)

        # No publisher should be created
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            await publish_log(sample_log)
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_publish_log_when_enabled(sample_log):
    """Test that publish_log works when streaming is enabled"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            mock_publisher = AsyncMock()
            mock_create.return_value.__aenter__.return_value = mock_publisher
            mock_create.return_value.__aexit__ = AsyncMock(return_value=None)

            await publish_log(sample_log)

            mock_create.assert_called_once()
            mock_publisher.publish_data.assert_called_once()

            # Check the published data
            call_args = mock_publisher.publish_data.call_args
            assert call_args[1]["data"] == sample_log.model_dump_json().encode()
            assert call_args[1]["attributes"]["log_id"] == str(sample_log.id)


@pytest.mark.asyncio
async def test_publish_log_with_id_none_in_message():
    """Test the case where log ID gets set to None in the message attributes"""
    log = Log(
        name="test.logger",
        level=20,
        message="Test message",
        timestamp=now("UTC"),
        flow_run_id=uuid4(),
        task_run_id=None,
    )

    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            mock_publisher = AsyncMock()
            mock_create.return_value.__aenter__.return_value = mock_publisher
            mock_create.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock the log ID to be None for testing the attributes logic
            with patch.object(log, "id", None):
                await publish_log(log)

                # Check that attributes are empty when ID is None
                call_args = mock_publisher.publish_data.call_args
                assert call_args[1]["attributes"] == {}


@pytest.mark.asyncio
async def test_publish_log_handles_errors(sample_log):
    """Test that publish_log handles errors gracefully"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            mock_create.side_effect = Exception("Publisher error")

            with patch("prefect.server.logs.messaging.logger.warning") as mock_warning:
                # Should not raise an exception
                await publish_log(sample_log)

                # Should log a warning
                mock_warning.assert_called_once()
                assert "Failed to publish log to stream" in str(mock_warning.call_args)


@pytest.mark.asyncio
async def test_publish_logs_when_disabled(sample_logs):
    """Test that publish_logs does nothing when streaming is disabled"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: False}):
        await publish_logs(sample_logs)

        # No publisher should be created
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            await publish_logs(sample_logs)
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_publish_logs_empty_list():
    """Test that publish_logs handles empty list"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            await publish_logs([])

            # Should return early without creating publisher
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_publish_logs_when_enabled(sample_logs):
    """Test that publish_logs works when streaming is enabled"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            mock_publisher = AsyncMock()
            mock_create.return_value.__aenter__.return_value = mock_publisher
            mock_create.return_value.__aexit__ = AsyncMock(return_value=None)

            await publish_logs(sample_logs)

            mock_create.assert_called_once()
            # Should be called once for each log
            assert mock_publisher.publish_data.call_count == len(sample_logs)


@pytest.mark.asyncio
async def test_publish_logs_handles_errors(sample_logs):
    """Test that publish_logs handles errors gracefully"""
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED: True}):
        with patch("prefect.server.logs.messaging.create_log_publisher") as mock_create:
            mock_create.side_effect = Exception("Publisher error")

            with patch("prefect.server.logs.messaging.logger.warning") as mock_warning:
                # Should not raise an exception
                await publish_logs(sample_logs)

                # Should log a warning
                mock_warning.assert_called_once()
                assert "Failed to publish logs to stream" in str(mock_warning.call_args)
