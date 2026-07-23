import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prefect_redis.client import _client_cache, clear_cached_clients
from prefect_redis.messaging import Consumer

from prefect.server.utilities.messaging import StopConsumer


@pytest.fixture(autouse=True)
async def flush_redis_database():
    """Override the autouse conftest fixture — these tests use mocks only."""
    yield


@pytest.fixture(autouse=True)
async def redis():
    """Override the autouse conftest fixture — these tests use mocks only."""
    yield


@pytest.mark.asyncio
async def test_clear_cached_clients_disconnects_pools():
    mock_client = MagicMock()
    mock_client.connection_pool = AsyncMock()
    mock_client.aclose = AsyncMock()

    mock_loop = asyncio.get_running_loop()
    cache_key = (MagicMock(), (), (), mock_loop)

    _client_cache[cache_key] = mock_client

    await clear_cached_clients()

    mock_client.connection_pool.disconnect.assert_awaited_once()
    mock_client.aclose.assert_awaited_once()
    assert len(_client_cache) == 0


@pytest.mark.asyncio
async def test_clear_cached_clients_handles_disconnect_errors():
    mock_client = MagicMock()
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.disconnect.side_effect = Exception(
        "failed to disconnect"
    )
    mock_client.aclose = AsyncMock()
    mock_client.aclose.side_effect = Exception("failed to close")

    mock_loop = asyncio.get_running_loop()
    cache_key = (MagicMock(), (), (), mock_loop)

    _client_cache[cache_key] = mock_client

    # Should not raise exception
    await clear_cached_clients()

    mock_client.connection_pool.disconnect.assert_awaited_once()
    mock_client.aclose.assert_awaited_once()
    assert len(_client_cache) == 0


@pytest.mark.asyncio
async def test_consumer_retries_on_os_error():
    consumer = Consumer(topic="test-topic")

    mock_client = AsyncMock()

    call_count = 0

    async def mock_ensure_stream_and_group(client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Simulated socket error")
        raise StopConsumer()

    with (
        patch(
            "prefect_redis.messaging.get_async_redis_client", return_value=mock_client
        ),
        patch.object(
            Consumer,
            "_ensure_stream_and_group",
            side_effect=mock_ensure_stream_and_group,
        ),
        patch(
            "prefect_redis.messaging.exponential_backoff_with_jitter", return_value=0.01
        ),
        patch("prefect_redis.messaging.clear_cached_clients") as mock_clear,
    ):
        mock_handler = AsyncMock()

        with pytest.raises(StopConsumer):
            await consumer.run(mock_handler)

        assert call_count == 2
        mock_clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_consumer_retries_on_connection_error():
    consumer = Consumer(topic="test-topic")

    mock_client = AsyncMock()

    call_count = 0

    async def mock_ensure_stream_and_group(client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Simulated connection error")
        raise StopConsumer()

    with (
        patch(
            "prefect_redis.messaging.get_async_redis_client", return_value=mock_client
        ),
        patch.object(
            Consumer,
            "_ensure_stream_and_group",
            side_effect=mock_ensure_stream_and_group,
        ),
        patch(
            "prefect_redis.messaging.exponential_backoff_with_jitter", return_value=0.01
        ),
        patch("prefect_redis.messaging.clear_cached_clients") as mock_clear,
    ):
        mock_handler = AsyncMock()

        with pytest.raises(StopConsumer):
            await consumer.run(mock_handler)

        assert call_count == 2
        mock_clear.assert_awaited_once()
