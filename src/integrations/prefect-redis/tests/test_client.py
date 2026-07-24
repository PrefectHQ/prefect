import asyncio
import warnings
from uuid import uuid4

import pytest
from prefect_redis.client import (
    RedisMessagingSettings,
    async_redis_from_settings,
    cluster_key_prefix,
    get_async_redis_client,
    is_cluster_url,
    managed_async_redis_client,
    normalize_cluster_url,
    redis_key,
)
from redis.asyncio import Redis
from redis.cluster import key_slot


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


def test_cluster_url_detection():
    assert is_cluster_url("redis+cluster://redis.example.com:6379")
    assert is_cluster_url("rediss+cluster://redis.example.com:6379")
    assert not is_cluster_url("redis://redis.example.com:6379")
    assert not is_cluster_url("rediss://redis.example.com:6379")
    assert not is_cluster_url("redis://host,[::1]:6379")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "redis+cluster://redis.example.com:6379",
            "redis://redis.example.com:6379",
        ),
        (
            "rediss+cluster://user:pass@redis.example.com:6380/0?protocol=3",
            "rediss://user:pass@redis.example.com:6380/0?protocol=3",
        ),
        (
            "redis://redis.example.com:6379/0",
            "redis://redis.example.com:6379/0",
        ),
    ],
)
def test_normalize_cluster_url(url: str, expected: str):
    assert normalize_cluster_url(url) == expected


def test_cluster_key_prefix_hash_tags_cluster_urls():
    assert (
        cluster_key_prefix(
            "prefect:events", url="redis+cluster://redis.example.com:6379"
        )
        == "{prefect:events}"
    )
    assert (
        cluster_key_prefix(
            "prefect:events", url="rediss+cluster://redis.example.com:6379"
        )
        == "{prefect:events}"
    )
    assert (
        cluster_key_prefix("prefect:events", url="redis://redis.example.com:6379")
        == "prefect:events"
    )


def test_redis_key_uses_cluster_aware_prefix():
    assert (
        redis_key(
            "prefect:events",
            "stream",
            url="redis+cluster://redis.example.com:6379",
        )
        == "{prefect:events}:stream"
    )
    assert (
        redis_key("prefect:events", "stream", url="redis://redis.example.com:6379")
        == "prefect:events:stream"
    )


def test_cluster_keys_share_hash_slot():
    keys = [
        redis_key(
            "prefect:events",
            suffix,
            url="redis+cluster://redis.example.com:6379",
        )
        for suffix in ["stream", "dlq", "dedupe:abc"]
    ]
    assert len({key_slot(key.encode()) for key in keys}) == 1


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


def test_get_async_redis_client_requires_running_loop():
    with pytest.raises(RuntimeError, match="running event loop"):
        get_async_redis_client()


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


async def test_get_async_redis_client_with_cluster_url_raises():
    """Cluster URLs are detected but not enabled until key work is complete."""
    with pytest.raises(NotImplementedError, match="Redis Cluster URLs"):
        get_async_redis_client(url="redis+cluster://clusterhost:7000")


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
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["host"] == "settingshost"
    assert conn_kwargs["port"] == 6383
    assert conn_kwargs["db"] == 5
    await client.aclose()


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


async def test_async_redis_from_settings_with_cluster_url_raises():
    """Settings URL cluster support is detection-only for now."""
    settings = RedisMessagingSettings(url="rediss+cluster://fromurl:6385")
    with pytest.raises(NotImplementedError, match="Redis Cluster URLs"):
        async_redis_from_settings(settings)


def test_redis_settings_connection_defaults():
    """Settings default to socket_timeout=None, socket_connect_timeout=None, protocol=2."""
    settings = RedisMessagingSettings()
    assert settings.socket_timeout is None
    assert settings.socket_connect_timeout is None
    assert settings.protocol == 2


def test_redis_settings_connection_from_env(monkeypatch: pytest.MonkeyPatch):
    """Connection settings can be configured via environment variables."""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_SOCKET_TIMEOUT", "10.0")
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_SOCKET_CONNECT_TIMEOUT", "3.5")
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_PROTOCOL", "3")
    settings = RedisMessagingSettings()
    assert settings.socket_timeout == 10.0
    assert settings.socket_connect_timeout == 3.5
    assert settings.protocol == 3


async def test_get_async_redis_client_default_socket_timeout():
    """Default clients have socket_timeout=None (no timeout) for redis-py 8 compat."""
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    await client.aclose()


async def test_get_async_redis_client_default_protocol():
    """Default clients use protocol=2 for older Redis/proxy compatibility."""
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


async def test_get_async_redis_client_explicit_socket_timeout():
    """Explicit socket_timeout overrides the settings default."""
    client = get_async_redis_client(socket_timeout=30.0, socket_connect_timeout=5.0)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 30.0
    assert conn_kwargs["socket_connect_timeout"] == 5.0
    await client.aclose()


async def test_get_async_redis_client_url_passes_socket_timeout():
    """socket_timeout/protocol are passed through the from_url path."""
    client = get_async_redis_client(url="redis://localhost:6379/0")
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


async def test_get_async_redis_client_url_query_overrides_keyword_defaults():
    """URL query params override keyword defaults (redis-py from_url behavior)."""
    client = get_async_redis_client(
        url="redis://localhost:6379/0?socket_timeout=7&socket_connect_timeout=3"
    )
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 7
    assert conn_kwargs["socket_connect_timeout"] == 3
    await client.aclose()


async def test_async_redis_from_settings_passes_connection_defaults():
    """async_redis_from_settings passes socket_timeout/protocol from settings."""
    settings = RedisMessagingSettings()
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


async def test_async_redis_from_settings_options_override():
    """Options kwargs override settings defaults in async_redis_from_settings."""
    settings = RedisMessagingSettings()
    client = async_redis_from_settings(settings, socket_timeout=15.0, protocol=3)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 15.0
    assert conn_kwargs["protocol"] == 3
    await client.aclose()


async def test_async_redis_from_settings_url_with_connection_defaults():
    """async_redis_from_settings with url passes connection defaults."""
    settings = RedisMessagingSettings(url="redis://localhost:6379/0")
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


async def test_get_async_redis_client_returns_uncached_clients():
    first = get_async_redis_client()
    second = get_async_redis_client()
    try:
        assert first is not second
    finally:
        await first.aclose()
        await second.aclose()


async def test_managed_async_redis_client_closes_connection(redis: Redis):
    client_name = f"prefect-test-{uuid4().hex}"

    async with managed_async_redis_client() as client:
        await client.ping()
        await client.client_setname(client_name)
        managed_client_ids = {
            client["id"]
            for client in await redis.client_list()
            if client["name"] == client_name
        }

    remaining_client_ids: set[str] = set()
    for _ in range(10):
        remaining_client_ids = {
            client["id"]
            for client in await redis.client_list()
            if client["name"] == client_name
        }
        if remaining_client_ids.isdisjoint(managed_client_ids):
            break
        await asyncio.sleep(0.1)

    assert managed_client_ids
    assert remaining_client_ids.isdisjoint(managed_client_ids)
