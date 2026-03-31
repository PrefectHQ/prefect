import warnings
from unittest.mock import MagicMock, patch

import pytest
from prefect_redis.client import (
    RedisMessagingSettings,
    _client_cache,
    async_redis_from_settings,
    close_all_cached_connections,
    get_async_redis_client,
)
from redis.asyncio import Redis


def test_redis_settings_defaults(isolated_redis_db_number: int):
    """Test that RedisSettings has expected defaults"""
    settings = RedisMessagingSettings()
    assert settings.url is None
    assert settings.host == "localhost"
    assert settings.port == 6379
    # Note: we override the db number in the conftest
    # to isolate redis db for xdist workers
    assert settings.db == isolated_redis_db_number
    assert settings.username == "default"
    assert settings.password == ""
    assert settings.health_check_interval == 20
    assert settings.ssl is False


def test_redis_settings_url():
    """Test that url field can be set directly"""
    settings = RedisMessagingSettings(url="redis://myhost:6380/2")
    assert settings.url == "redis://myhost:6380/2"


def test_redis_settings_url_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test that url can be configured via environment variable"""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", "redis://envhost:6381/3")
    settings = RedisMessagingSettings()
    assert settings.url == "redis://envhost:6381/3"


def test_redis_settings_url_warns_on_conflicting_fields():
    """When url and discrete fields are both set, warn that discrete fields are ignored"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        RedisMessagingSettings(url="redis://myhost:6380/2", host="other-host")

    assert len(caught) == 1
    assert "host" in str(caught[0].message)
    assert "ignored" in str(caught[0].message)


def test_redis_settings_url_no_warning_with_defaults(monkeypatch: pytest.MonkeyPatch):
    """No warning when url is set but discrete fields are all defaults"""
    monkeypatch.delenv("PREFECT_REDIS_MESSAGING_DB", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        RedisMessagingSettings(url="redis://myhost:6380/2")

    assert len(caught) == 0


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


async def test_get_async_redis_client_with_url():
    """Test that get_async_redis_client uses from_url when url is provided"""
    client = get_async_redis_client(url="redis://urlhost:6382/4")
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "urlhost"
    assert conn_kwargs["port"] == 6382
    assert conn_kwargs["db"] == 4
    await client.aclose()


async def test_get_async_redis_client_url_with_credentials():
    """Test that Redis URL with embedded credentials works"""
    client = get_async_redis_client(url="redis://myuser:mypass@urlhost:6382/4")
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "urlhost"
    assert conn_kwargs["port"] == 6382
    assert conn_kwargs["db"] == 4
    assert conn_kwargs["username"] == "myuser"
    assert conn_kwargs["password"] == "mypass"
    await client.aclose()


async def test_get_async_redis_client_url_from_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that url from settings is used when no explicit url param is passed"""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", "redis://settingshost:6383/5")
    # Clear cache so the env var is picked up by a fresh RedisMessagingSettings
    _client_cache.clear()
    try:
        client = get_async_redis_client()
        conn_kwargs = client.connection_pool.connection_kwargs
        assert conn_kwargs["host"] == "settingshost"
        assert conn_kwargs["port"] == 6383
        assert conn_kwargs["db"] == 5
        await client.aclose()
    finally:
        # The no-args cache entry now points at the URL-based client.
        # Clear it so subsequent tests (and the autouse redis fixture)
        # get a client matching the real env again.
        _client_cache.clear()


async def test_get_async_redis_client_explicit_url_overrides_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit url param takes precedence over PREFECT_REDIS_MESSAGING_URL"""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", "redis://settingshost:6383/5")
    client = get_async_redis_client(url="redis://explicithost:6384/6")
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "explicithost"
    assert conn_kwargs["port"] == 6384
    assert conn_kwargs["db"] == 6
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


async def test_async_redis_from_settings_with_url():
    """Test creating Redis client from settings with url"""
    settings = RedisMessagingSettings(url="redis://fromurl:6385/7")
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "fromurl"
    assert conn_kwargs["port"] == 6385
    assert conn_kwargs["db"] == 7
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
