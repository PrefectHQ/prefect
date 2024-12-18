from unittest.mock import MagicMock, patch

from prefect_redis.client import (
    RedisMessagingSettings,
    async_redis_from_settings,
    close_all_cached_connections,
    get_async_redis_client,
)
from redis.asyncio import Redis


def test_redis_settings_defaults(isolated_redis_db_number: int):
    """Test that RedisSettings has expected defaults"""
    settings = RedisMessagingSettings()
    assert settings.host == "localhost"
    assert settings.port == 6379
    # Note: we override the db number in the conftest
    # to isolate redis db for xdist workers
    assert settings.db == isolated_redis_db_number
    assert settings.username == "default"
    assert settings.password == ""
    assert settings.health_check_interval == 20
    assert settings.ssl is False


async def test_get_async_redis_client_defaults():
    """Test that get_async_redis_client creates client with default settings"""
    client = get_async_redis_client()
    assert isinstance(client, Redis)
    assert client.connection_pool.connection_kwargs["host"] == "localhost"
    assert client.connection_pool.connection_kwargs["port"] == 6379
    await client.aclose()


async def test_get_async_redis_client_custom_params():
    """Test that get_async_redis_client respects custom parameters"""
    client = get_async_redis_client(
        host="custom.host",
        port=6380,
        db=1,
        username="custom_user",
        password="secret",
    )
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "custom.host"
    assert conn_kwargs["port"] == 6380
    assert conn_kwargs["db"] == 1
    assert conn_kwargs["username"] == "custom_user"
    assert conn_kwargs["password"] == "secret"
    await client.aclose()


async def test_async_redis_from_settings():
    """Test creating Redis client from settings object"""
    settings = RedisMessagingSettings(
        host="settings.host",
        port=6381,
        username="settings_user",
    )
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "settings.host"
    assert conn_kwargs["port"] == 6381
    assert conn_kwargs["username"] == "settings_user"
    await client.aclose()


@patch("prefect_redis.client._client_cache")
def test_close_all_cached_connections(mock_cache):
    """Test that close_all_cached_connections properly closes all clients"""
    mock_client = MagicMock()
    mock_loop = MagicMock()
    mock_loop.is_closed.return_value = False

    # Mock the coroutines that would be awaited
    mock_loop.run_until_complete.return_value = None

    mock_cache.items.return_value = [((None, None, None, mock_loop), mock_client)]

    close_all_cached_connections()

    # Verify run_until_complete was called twice (for disconnect and close)
    assert mock_loop.run_until_complete.call_count == 2
