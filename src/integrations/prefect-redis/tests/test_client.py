import asyncio
import socket
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from prefect_redis.client import (
    RedisMessagingSettings,
    _client_cache,
    _force_close_client_sockets,
    async_redis_from_settings,
    clear_cached_clients,
    close_all_cached_connections,
    cluster_key_prefix,
    get_async_redis_client,
    is_cluster_url,
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
    _client_cache.clear()
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


async def test_async_redis_from_settings_with_cluster_url_raises():
    """Settings URL cluster support is detection-only for now."""
    _client_cache.clear()
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
    _client_cache.clear()
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    await client.aclose()
    _client_cache.clear()


async def test_get_async_redis_client_default_protocol():
    """Default clients use protocol=2 for older Redis/proxy compatibility."""
    _client_cache.clear()
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()
    _client_cache.clear()


async def test_get_async_redis_client_explicit_socket_timeout():
    """Explicit socket_timeout overrides the settings default."""
    _client_cache.clear()
    client = get_async_redis_client(socket_timeout=30.0, socket_connect_timeout=5.0)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 30.0
    assert conn_kwargs["socket_connect_timeout"] == 5.0
    await client.aclose()
    _client_cache.clear()


async def test_get_async_redis_client_url_passes_socket_timeout():
    """socket_timeout/protocol are passed through the from_url path."""
    _client_cache.clear()
    client = get_async_redis_client(url="redis://localhost:6379/0")
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()
    _client_cache.clear()


async def test_get_async_redis_client_url_query_overrides_keyword_defaults():
    """URL query params override keyword defaults (redis-py from_url behavior)."""
    _client_cache.clear()
    client = get_async_redis_client(
        url="redis://localhost:6379/0?socket_timeout=7&socket_connect_timeout=3"
    )
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 7
    assert conn_kwargs["socket_connect_timeout"] == 3
    await client.aclose()
    _client_cache.clear()


async def test_async_redis_from_settings_passes_connection_defaults():
    """async_redis_from_settings passes socket_timeout/protocol from settings."""
    _client_cache.clear()
    settings = RedisMessagingSettings()
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()
    _client_cache.clear()


async def test_async_redis_from_settings_options_override():
    """Options kwargs override settings defaults in async_redis_from_settings."""
    _client_cache.clear()
    settings = RedisMessagingSettings()
    client = async_redis_from_settings(settings, socket_timeout=15.0, protocol=3)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs["socket_timeout"] == 15.0
    assert conn_kwargs["protocol"] == 3
    await client.aclose()
    _client_cache.clear()


async def test_async_redis_from_settings_url_with_connection_defaults():
    """async_redis_from_settings with url passes connection defaults."""
    _client_cache.clear()
    settings = RedisMessagingSettings(url="redis://localhost:6379/0")
    client = async_redis_from_settings(settings)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()
    _client_cache.clear()


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


def _live_writers(client: Redis) -> list[object]:
    """Return connection objects in a client's pool that still hold a writer."""
    pool = client.connection_pool
    connections = list(pool._available_connections) + list(pool._in_use_connections)
    return [conn for conn in connections if getattr(conn, "_writer", None) is not None]


def test_cached_clients_are_evicted_when_their_loop_closes(isolated_redis_db_number):
    """Regression for the per-event-loop client leak (GitHub #22442).

    Each `asyncio.run` creates a fresh loop; the client cached for a loop that
    has since closed must be evicted (and its socket released) rather than
    accumulating without bound.
    """
    _client_cache.clear()

    async def touch() -> None:
        client = get_async_redis_client()
        await client.ping()  # force a real connection on THIS event loop

    try:
        for _ in range(10):
            asyncio.run(touch())
            # Never more than one entry: the just-closed loop's client is evicted
            # on the next `cached` call (and the current run leaves one behind).
            assert len(_client_cache) <= 1
    finally:
        close_all_cached_connections()

    assert len(_client_cache) == 0


def test_close_all_cached_connections_releases_closed_loop_clients(
    isolated_redis_db_number,
):
    """close_all_cached_connections must force-close clients from dead loops."""
    _client_cache.clear()

    captured: list[Redis] = []

    async def touch() -> None:
        client = get_async_redis_client()
        await client.ping()
        captured.append(client)

    # Populate the cache with a client bound to a now-closed loop, without
    # triggering the proactive eviction that `get_async_redis_client` performs.
    asyncio.run(touch())
    client = captured[0]
    assert _live_writers(client), "expected a live connection before cleanup"

    close_all_cached_connections()

    assert len(_client_cache) == 0
    assert _live_writers(client) == [], "sockets from the closed loop were not released"


def test_clear_cached_clients_releases_closed_loop_clients(isolated_redis_db_number):
    """clear_cached_clients force-closes clients whose loop has already closed."""
    _client_cache.clear()

    captured: list[Redis] = []

    async def touch() -> None:
        client = get_async_redis_client()
        await client.ping()
        captured.append(client)

    asyncio.run(touch())  # leaves a client bound to a now-closed loop in the cache
    closed_loop_client = captured[0]
    assert _live_writers(closed_loop_client), (
        "expected a live connection before cleanup"
    )

    asyncio.run(clear_cached_clients())

    assert len(_client_cache) == 0
    assert _live_writers(closed_loop_client) == [], (
        "sockets from the closed loop were not released"
    )


async def test_clear_cached_clients_drops_live_client_without_closing(
    isolated_redis_db_number,
):
    """clear_cached_clients drops a live-loop client from the cache but must not
    force-close its socket: the fd is still registered with the running loop's
    selector, and the caller simply fetches a fresh client afterwards.
    """
    _client_cache.clear()

    client = get_async_redis_client()
    await client.ping()
    assert _live_writers(client), "expected a live connection before cleanup"

    await clear_cached_clients()

    assert len(_client_cache) == 0
    assert _live_writers(client), "live-loop client should not be force-closed"

    await client.aclose()


def _fake_client_with_transport(transport: object) -> Redis:
    """Build a stand-in Redis whose pool holds one connection with `transport`."""
    conn = SimpleNamespace(
        _writer=SimpleNamespace(transport=transport), _reader=object()
    )
    pool = SimpleNamespace(_available_connections=[conn], _in_use_connections=[])
    return SimpleNamespace(connection_pool=pool)  # type: ignore[return-value]


def test_force_close_releases_tls_transport_socket():
    """TLS transports have no `_sock`; the fd lives on the wrapped transport.

    An asyncio SSL transport (`rediss://` / `ssl=True`) exposes no `_sock`; the
    real socket lives on the selector transport reached via
    `_ssl_protocol._transport`. If the force-close path doesn't follow that
    chain it silently leaks the fd (GH #22443).
    """
    left, right = socket.socketpair()
    right.close()

    # Mimic asyncio's _SSLProtocolTransport -> SSLProtocol -> selector transport.
    ssl_transport = SimpleNamespace(
        _ssl_protocol=SimpleNamespace(_transport=SimpleNamespace(_sock=left))
    )
    assert not hasattr(ssl_transport, "_sock")

    _force_close_client_sockets(_fake_client_with_transport(ssl_transport))

    assert left.fileno() == -1, "TLS transport socket was not closed"


def test_force_close_releases_plain_transport_socket():
    """Plain selector transports expose the socket directly as `_sock`."""
    left, right = socket.socketpair()
    right.close()

    plain_transport = SimpleNamespace(_sock=left)

    _force_close_client_sockets(_fake_client_with_transport(plain_transport))

    assert left.fileno() == -1, "plain transport socket was not closed"
