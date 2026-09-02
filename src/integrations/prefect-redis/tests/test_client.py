import asyncio
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prefect_redis.client import (
    RedisMessagingSettings,
    _client_cache,
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


@patch("prefect_redis.client.RedisMessagingSettings")
async def test_cluster_key_prefix_caches_settings_until_clients_are_cleared(
    settings: MagicMock,
):
    settings.return_value.url = None

    assert cluster_key_prefix("prefect:events") == "prefect:events"
    assert cluster_key_prefix("prefect:events") == "prefect:events"
    settings.assert_called_once_with()

    await clear_cached_clients()

    assert cluster_key_prefix("prefect:events") == "prefect:events"
    assert settings.call_count == 2


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


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"ssl": False}, {"ssl": False}),
        ({"port": 0}, {"port": 0}),
        ({"db": 0}, {"db": 0}),
        ({"health_check_interval": 0}, {"health_check_interval": 0}),
    ],
)
def test_get_async_redis_client_preserves_explicit_falsy_overrides(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, bool | int],
    expected: dict[str, bool | int],
):
    settings = RedisMessagingSettings(
        ssl=True, port=6380, db=1, health_check_interval=30
    )
    redis = MagicMock()
    monkeypatch.setattr("prefect_redis.client.RedisMessagingSettings", lambda: settings)
    monkeypatch.setattr("prefect_redis.client.Redis", redis)
    _client_cache.clear()

    try:
        get_async_redis_client(**overrides)

        for key, value in expected.items():
            assert redis.call_args.kwargs[key] == value
    finally:
        _client_cache.clear()


def test_get_async_redis_client_none_overrides_inherit_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = RedisMessagingSettings(
        ssl=True, port=6380, db=1, health_check_interval=30
    )
    redis = MagicMock()
    monkeypatch.setattr("prefect_redis.client.RedisMessagingSettings", lambda: settings)
    monkeypatch.setattr("prefect_redis.client.Redis", redis)
    _client_cache.clear()

    try:
        get_async_redis_client()

        expected = {
            "ssl": True,
            "port": 6380,
            "db": 1,
            "health_check_interval": 30,
        }
        for key, value in expected.items():
            assert redis.call_args.kwargs[key] == value
    finally:
        _client_cache.clear()


def test_get_async_redis_client_url_preserves_explicit_zero_health_check_interval(
    monkeypatch: pytest.MonkeyPatch,
):
    redis = MagicMock()
    monkeypatch.setattr("prefect_redis.client.Redis", redis)
    _client_cache.clear()

    try:
        get_async_redis_client(url="redis://localhost:6379/0", health_check_interval=0)

        assert redis.from_url.call_args.kwargs["health_check_interval"] == 0
    finally:
        _client_cache.clear()


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
    """Settings default to socket_timeout=60.0, socket_connect_timeout=10.0, protocol=2."""
    settings = RedisMessagingSettings()
    assert settings.socket_timeout == 60.0
    assert settings.socket_connect_timeout == 10.0
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
    """Default clients have socket_timeout=60.0, socket_connect_timeout=10.0."""
    _client_cache.clear()
    client = get_async_redis_client()
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("socket_timeout") == 60.0
    assert conn_kwargs.get("socket_connect_timeout") == 10.0
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
    assert conn_kwargs.get("socket_timeout") == 60.0
    assert conn_kwargs.get("socket_connect_timeout") == 10.0
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
    assert conn_kwargs.get("socket_timeout") == 60.0
    assert conn_kwargs.get("socket_connect_timeout") == 10.0
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
    assert conn_kwargs.get("socket_timeout") == 60.0
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


class TestClearCachedClients:
    """Regression tests for clear_cached_clients().

    clear_cached_clients() is called on every reconnect attempt after a
    RedisError (see messaging.py's consumer loop). It must actually close
    each evicted client's connections -- including ones stuck "in use" from
    a hung operation -- or those sockets leak until the pool's connection
    cap is exhausted, permanently, even once Redis is healthy again.
    """

    def _cached_client(
        self, loop: asyncio.AbstractEventLoop
    ) -> tuple[tuple, MagicMock]:
        client = MagicMock()
        client.aclose = AsyncMock()
        key = (get_async_redis_client, (), (), loop)
        _client_cache[key] = client
        return key, client

    async def test_clear_cached_clients_closes_current_loop_clients(self):
        key, client = self._cached_client(asyncio.get_running_loop())

        await clear_cached_clients()

        client.aclose.assert_awaited_once()
        assert key not in _client_cache

    async def test_clear_cached_clients_leaves_other_loop_clients(self):
        other_loop = asyncio.new_event_loop()
        key, client = self._cached_client(other_loop)
        try:
            await clear_cached_clients()

            client.aclose.assert_not_awaited()
            assert _client_cache[key] is client
        finally:
            del _client_cache[key]
            other_loop.close()

    async def test_clear_cached_clients_tolerates_close_failures(self):
        """A dead connection failing to close must not abort the recovery
        path that called clear_cached_clients()."""
        key, client = self._cached_client(asyncio.get_running_loop())
        client.aclose.side_effect = ConnectionError("gone")

        await clear_cached_clients()  # must not raise

        assert key not in _client_cache

    async def test_clear_cached_clients_is_safe_under_concurrent_caching(self):
        """A second consumer racing to cache a client mid-close must not be
        lost or hit a 'dictionary changed size during iteration' error."""
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_aclose():
            started.set()
            await release.wait()

        key, client = self._cached_client(asyncio.get_running_loop())
        client.aclose.side_effect = slow_aclose

        task = asyncio.ensure_future(clear_cached_clients())
        await started.wait()

        other_key, other_client = self._cached_client(asyncio.get_running_loop())
        try:
            release.set()
            await task  # must not raise

            assert _client_cache[other_key] is other_client
        finally:
            _client_cache.pop(other_key, None)

    async def test_clear_cached_clients_closes_none_loop_clients(self):
        """A client cached from sync context (no running loop) has a None
        loop key. Nothing else ever closes these, so clear_cached_clients()
        must reap them on whatever loop is running now."""
        key, client = self._cached_client(None)

        await clear_cached_clients()

        client.aclose.assert_awaited_once()
        assert key not in _client_cache

    async def test_clear_cached_clients_with_client_arg_targets_only_that_client(
        self,
    ):
        """One broker's outage must not force-close a healthy client cached
        for a different endpoint."""
        loop = asyncio.get_running_loop()

        failed_client = MagicMock()
        failed_client.aclose = AsyncMock()
        failed_key = (get_async_redis_client, (), (("url", "redis://failed"),), loop)
        _client_cache[failed_key] = failed_client

        healthy_client = MagicMock()
        healthy_client.aclose = AsyncMock()
        healthy_key = (get_async_redis_client, (), (("url", "redis://healthy"),), loop)
        _client_cache[healthy_key] = healthy_client

        try:
            await clear_cached_clients(client=failed_client)

            failed_client.aclose.assert_awaited_once()
            assert failed_key not in _client_cache
            healthy_client.aclose.assert_not_awaited()
            assert _client_cache[healthy_key] is healthy_client
        finally:
            _client_cache.pop(failed_key, None)
            _client_cache.pop(healthy_key, None)

    async def test_clear_cached_clients_releases_in_use_connections(self):
        """End-to-end regression test against a real Redis: prove the fix
        actually reaps a connection stuck in-use, not just that the cache
        dict gets emptied (which passes even without the fix)."""
        client = get_async_redis_client()
        await client.ping()

        pool = client.connection_pool
        leaked_connection = await pool.get_connection()
        assert leaked_connection in pool._in_use_connections
        assert leaked_connection.is_connected

        await clear_cached_clients()

        assert not leaked_connection.is_connected
