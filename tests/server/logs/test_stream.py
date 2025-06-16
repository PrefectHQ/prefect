import asyncio
import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from prefect.server.logs.stream import (
    LogDistributor,
    distributor,
    filters,
    log_matches_filter,
    logs,
    start_distributor,
    stop_distributor,
    subscribed,
    subscribers,
)
from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import (
    LogFilter,
    LogFilterFlowRunId,
    LogFilterLevel,
    LogFilterTaskRunId,
    LogFilterTimestamp,
)
from prefect.settings import PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED, temporary_settings
from prefect.types._datetime import now


@pytest.fixture
def sample_log1():
    """A sample log record"""
    return Log(
        id=uuid4(),
        name="test.logger",
        level=20,  # INFO
        message="Test message 1",
        timestamp=now("UTC"),
        flow_run_id=uuid4(),
        task_run_id=uuid4(),
    )


@pytest.fixture
def sample_log2():
    """Another sample log record"""
    return Log(
        id=uuid4(),
        name="test.logger2",
        level=40,  # ERROR
        message="Test message 2",
        timestamp=now("UTC") + datetime.timedelta(seconds=1),
        flow_run_id=uuid4(),
        task_run_id=None,
    )


def test_log_distributor_service_properties():
    """Test that LogDistributor has the expected service properties"""
    assert LogDistributor.name == "LogDistributor"
    assert (
        LogDistributor.environment_variable_name()
        == "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED"
    )


def test_log_matches_filter_level(sample_log1):
    """Test log filtering by level"""
    # Should match - log level 20 >= 20
    filter = LogFilter(level=LogFilterLevel(ge_=20))
    assert log_matches_filter(sample_log1, filter)

    # Should not match - log level 20 < 30
    filter = LogFilter(level=LogFilterLevel(ge_=30))
    assert not log_matches_filter(sample_log1, filter)

    # Should match - log level 20 <= 30
    filter = LogFilter(level=LogFilterLevel(le_=30))
    assert log_matches_filter(sample_log1, filter)

    # Should not match - log level 20 > 10
    filter = LogFilter(level=LogFilterLevel(le_=10))
    assert not log_matches_filter(sample_log1, filter)


def test_log_matches_filter_timestamp(sample_log1):
    """Test log filtering by timestamp"""
    before_time = sample_log1.timestamp + datetime.timedelta(seconds=1)
    after_time = sample_log1.timestamp - datetime.timedelta(seconds=1)

    # Should match - log timestamp is before the filter time
    filter = LogFilter(timestamp=LogFilterTimestamp(before_=before_time))
    assert log_matches_filter(sample_log1, filter)

    # Should not match - log timestamp is after the filter time
    filter = LogFilter(timestamp=LogFilterTimestamp(before_=after_time))
    assert not log_matches_filter(sample_log1, filter)

    # Should match - log timestamp is after the filter time
    filter = LogFilter(timestamp=LogFilterTimestamp(after_=after_time))
    assert log_matches_filter(sample_log1, filter)


def test_log_matches_filter_flow_run_id(sample_log1):
    """Test log filtering by flow_run_id"""
    # Should match - flow_run_id is in the list
    filter = LogFilter(flow_run_id=LogFilterFlowRunId(any_=[sample_log1.flow_run_id]))
    assert log_matches_filter(sample_log1, filter)

    # Should not match - flow_run_id is not in the list
    filter = LogFilter(flow_run_id=LogFilterFlowRunId(any_=[uuid4()]))
    assert not log_matches_filter(sample_log1, filter)


def test_log_matches_filter_task_run_id(sample_log1, sample_log2):
    """Test log filtering by task_run_id"""
    # Should match - task_run_id is in the list
    filter = LogFilter(task_run_id=LogFilterTaskRunId(any_=[sample_log1.task_run_id]))
    assert log_matches_filter(sample_log1, filter)

    # Should not match - task_run_id is not in the list
    filter = LogFilter(task_run_id=LogFilterTaskRunId(any_=[uuid4()]))
    assert not log_matches_filter(sample_log1, filter)

    # Test null filtering - sample_log2 has None task_run_id
    filter = LogFilter(task_run_id=LogFilterTaskRunId(is_null_=True))
    assert log_matches_filter(sample_log2, filter)
    assert not log_matches_filter(sample_log1, filter)

    filter = LogFilter(task_run_id=LogFilterTaskRunId(is_null_=False))
    assert not log_matches_filter(sample_log2, filter)
    assert log_matches_filter(sample_log1, filter)


def test_log_matches_filter_empty():
    """Test that empty filter matches all logs"""
    log = Log(
        id=uuid4(),
        name="test",
        level=20,
        message="test",
        timestamp=now("UTC"),
        flow_run_id=None,
        task_run_id=None,
    )

    empty_filter = LogFilter()
    assert log_matches_filter(log, empty_filter)


@pytest.mark.asyncio
async def test_subscribed_context_manager(sample_log1):
    """Test the subscribed context manager"""
    filter = LogFilter()

    async with subscribed(filter) as queue:
        assert queue is not None
        assert queue in subscribed.__wrapped__.__globals__["subscribers"]
        assert subscribed.__wrapped__.__globals__["filters"][queue] == filter

    # Should be cleaned up after context exit
    assert queue not in subscribed.__wrapped__.__globals__["subscribers"]
    assert queue not in subscribed.__wrapped__.__globals__["filters"]


@pytest.mark.asyncio
async def test_logs_context_manager():
    """Test the logs context manager returns an async iterable"""
    filter = LogFilter()

    async with logs(filter) as log_stream:
        assert hasattr(log_stream, "__aiter__")
        # We can't easily test the actual streaming without setting up
        # the full messaging system, but we can verify the structure


@pytest.mark.asyncio
async def test_logs_consume_timeout():
    """Test that the logs consumer yields None on timeout"""
    filter = LogFilter()

    async with logs(filter) as log_stream:
        # Mock the queue.get to raise TimeoutError
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            async for log in log_stream:
                assert log is None
                break  # Exit after first None


@pytest.fixture
async def mock_subscriber():
    """Fixture that provides a mock subscriber and cleans up automatically"""
    queue = asyncio.Queue()
    filter = LogFilter()

    subscribers.add(queue)
    filters[queue] = filter

    yield queue, filter

    # Cleanup
    if queue in subscribers:
        subscribers.remove(queue)
    if queue in filters:
        del filters[queue]


@pytest.mark.asyncio
async def test_distributor_message_handler(sample_log1, mock_subscriber):
    """Test the distributor message handler"""
    queue, filter = mock_subscriber

    # Create a mock message
    mock_message = Mock()
    mock_message.data = sample_log1.model_dump_json().encode()
    mock_message.attributes = {"log_id": "test"}

    async with distributor() as handler:
        await handler(mock_message)

        # Should have put the log in the queue
        assert not queue.empty()
        log = await queue.get()
        assert log.message == "Test message 1"


@pytest.mark.asyncio
async def test_distributor_message_handler_no_attributes():
    """Test distributor handles messages without attributes"""
    # Create a mock message without attributes
    mock_message = Mock()
    mock_message.data = b"test data"
    mock_message.attributes = None

    async with distributor() as handler:
        # Should not raise an exception
        await handler(mock_message)


@pytest.mark.asyncio
async def test_distributor_message_handler_invalid_json():
    """Test distributor handles invalid JSON gracefully"""
    # Create a mock message with invalid JSON
    mock_message = Mock()
    mock_message.data = b"invalid json"
    mock_message.attributes = {"test": "value"}

    # Need at least one subscriber for the parsing to be attempted
    queue = asyncio.Queue()
    subscribers.add(queue)

    try:
        with patch("prefect.server.logs.stream.logger.warning") as mock_warning:
            async with distributor() as handler:
                await handler(mock_message)

                # Should log a warning about parsing failure
                mock_warning.assert_called_once()
    finally:
        # Clean up
        if queue in subscribers:
            subscribers.remove(queue)


@pytest.fixture
async def mock_subscriber_with_filter():
    """Fixture that provides a mock subscriber with a restrictive filter"""
    queue = asyncio.Queue()
    filter = LogFilter(level=LogFilterLevel(ge_=50))  # ERROR level or higher

    subscribers.add(queue)
    filters[queue] = filter

    yield queue, filter

    # Cleanup
    if queue in subscribers:
        subscribers.remove(queue)
    if queue in filters:
        del filters[queue]


@pytest.mark.asyncio
async def test_distributor_message_handler_filtered_out(
    sample_log1, mock_subscriber_with_filter
):
    """Test distributor filters out logs that don't match"""
    queue, filter = mock_subscriber_with_filter

    # Create a mock message
    mock_message = Mock()
    mock_message.data = sample_log1.model_dump_json().encode()
    mock_message.attributes = {"log_id": "test"}

    async with distributor() as handler:
        await handler(mock_message)

        # Queue should be empty because log was filtered out
        assert queue.empty()


@pytest.fixture
async def mock_full_subscriber():
    """Fixture that provides a mock subscriber with a full queue"""
    queue = asyncio.Queue(maxsize=1)
    await queue.put("dummy")  # Fill the queue
    filter = LogFilter()

    subscribers.add(queue)
    filters[queue] = filter

    yield queue, filter

    # Cleanup
    if queue in subscribers:
        subscribers.remove(queue)
    if queue in filters:
        del filters[queue]


@pytest.mark.asyncio
async def test_distributor_message_handler_queue_full(
    sample_log1, mock_full_subscriber
):
    """Test distributor handles full queues gracefully"""
    queue, filter = mock_full_subscriber

    # Create a mock message
    mock_message = Mock()
    mock_message.data = sample_log1.model_dump_json().encode()
    mock_message.attributes = {"log_id": "test"}

    async with distributor() as handler:
        # Should not raise an exception even with full queue
        await handler(mock_message)


@pytest.mark.asyncio
async def test_start_stop_distributor():
    """Test starting and stopping the distributor"""
    from prefect.server.logs import stream

    # Ensure clean initial state
    await stop_distributor()

    try:
        # Initially should be None
        assert stream._distributor_task is None

        # Start distributor
        await start_distributor()

        assert stream._distributor_task is not None
        assert not stream._distributor_task.done()

    finally:
        # Stop distributor
        await stop_distributor()

        assert stream._distributor_task is None


@pytest.mark.asyncio
async def test_log_distributor_service_lifecycle():
    """Test LogDistributor service lifecycle"""
    # Test that service is disabled by default
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED: False}):
        assert not LogDistributor.enabled()

    # Test that service can be enabled
    with temporary_settings({PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED: True}):
        assert LogDistributor.enabled()


def test_log_distributor_service_class_methods():
    """Test LogDistributor service class methods"""
    # Test service name
    assert LogDistributor.name == "LogDistributor"

    # Test environment variable name
    assert (
        LogDistributor.environment_variable_name()
        == "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED"
    )

    # Test that service_settings raises NotImplementedError
    with pytest.raises(NotImplementedError):
        LogDistributor.service_settings()


@pytest.mark.asyncio
async def test_start_distributor_already_started():
    """Test starting distributor when already started"""
    from prefect.server.logs import stream

    # Ensure clean state
    await stop_distributor()

    try:
        # Start distributor first time
        await start_distributor()

        # Get the current task
        first_task = stream._distributor_task
        assert first_task is not None

        # Start again - should not create a new task
        await start_distributor()

        assert stream._distributor_task is first_task  # Should be the same task

    finally:
        # Clean up
        await stop_distributor()


@pytest.mark.asyncio
async def test_stop_distributor_not_started():
    """Test stopping distributor when not started"""
    # Ensure clean state first
    await stop_distributor()

    # Should not raise an exception when stopping again
    await stop_distributor()


def test_log_matches_filter_complex_flow_run_id_case():
    """Test flow_run_id filtering edge case"""
    log = Log(
        id=uuid4(),
        name="test",
        level=20,
        message="test",
        timestamp=now("UTC"),
        flow_run_id=None,  # No flow run ID
        task_run_id=None,
    )

    # Filter with flow_run_id requirement - should not match
    filter = LogFilter(flow_run_id=LogFilterFlowRunId(any_=[uuid4()]))
    assert not log_matches_filter(log, filter)


def test_log_matches_filter_timestamp_after(sample_log1):
    """Test timestamp filtering with after condition"""
    # Should not match - log timestamp is before the filter time
    after_time = sample_log1.timestamp + datetime.timedelta(seconds=1)
    filter = LogFilter(timestamp=LogFilterTimestamp(after_=after_time))
    assert not log_matches_filter(sample_log1, filter)


@pytest.mark.asyncio
async def test_logs_consumer_continue_after_timeout():
    """Test that logs consumer continues after timeout"""
    filter = LogFilter()

    async with logs(filter) as log_stream:
        # Create an iterator to test the continue path
        iterator = log_stream.__aiter__()

        # Mock wait_for to raise TimeoutError then return a log
        call_count = 0

        async def mock_wait_for(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            else:
                # Return a dummy log for the second call
                return Log(
                    id=uuid4(),
                    name="test",
                    level=20,
                    message="test",
                    timestamp=now("UTC"),
                    flow_run_id=None,
                    task_run_id=None,
                )

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            # First call should return None (timeout)
            result1 = await iterator.__anext__()
            assert result1 is None

            # Second call should return the log
            result2 = await iterator.__anext__()
            assert result2 is not None
            assert result2.message == "test"


def test_log_matches_filter_flow_run_id_none_edge_case():
    """Test flow_run_id filtering when log has None flow_run_id"""
    log = Log(
        id=uuid4(),
        name="test",
        level=20,
        message="test",
        timestamp=now("UTC"),
        flow_run_id=None,  # This is the key case we're testing
        task_run_id=None,
    )

    # When flow_run_id is None and filter requires specific IDs, should not match
    target_id = uuid4()
    filter = LogFilter(flow_run_id=LogFilterFlowRunId(any_=[target_id]))
    assert not log_matches_filter(log, filter)


@pytest.mark.asyncio
async def test_distributor_message_handler_no_subscribers(sample_log1):
    """Test distributor early exit when no subscribers"""
    # Ensure no subscribers exist
    subscribers.clear()

    # Create a valid message
    mock_message = Mock()
    mock_message.data = sample_log1.model_dump_json().encode()
    mock_message.attributes = {"log_id": "test"}

    async with distributor() as handler:
        # Should exit early since there are no subscribers
        await handler(mock_message)
        # No assertion needed - just testing that it doesn't crash


@pytest.mark.asyncio
async def test_log_distributor_service_stop():
    """Test LogDistributor service stop method"""
    distributor_service = LogDistributor()

    with patch(
        "prefect.server.logs.stream.stop_distributor", new_callable=AsyncMock
    ) as mock_stop:
        await distributor_service.stop()
        mock_stop.assert_called_once()
