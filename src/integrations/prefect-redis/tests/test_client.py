import asyncio
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prefect_redis.client import (
    RedisMessagingSettings,
    _client_cache,
    _running_loop,
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
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError


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
    """Settings default to non-None socket timeouts so reads/connects fail fast."""
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
    """Default clients have non-None socket timeouts so the pool recovers after an outage."""
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


@pytest.mark.parametrize(
    "make_client",
    [
        pytest.param(lambda: get_async_redis_client(), id="host_port"),
        pytest.param(
            lambda: get_async_redis_client(url="redis://localhost:6379/0"),
            id="from_url",
        ),
        pytest.param(
            lambda: async_redis_from_settings(RedisMessagingSettings()),
            id="from_settings",
        ),
    ],
)
async def test_client_uses_bounded_retry_on_both_construction_paths(make_client):
    """Every construction path bounds retries and does not retry read timeouts.

    redis-py 8 defaults commands to 10 retries and holds the connection across
    all of them (so a dead broker occupies a pool slot for ~11 socket timeouts),
    while `Redis.from_url` gets a different policy. Both paths must instead use
    the same small bounded retry that only covers connection errors so blocking
    reads fail fast into the consumer's reconnect loop (OSS-8071 / #22478).
    """
    _client_cache.clear()
    client = make_client()
    try:
        retry = client.connection_pool.connection_kwargs.get("retry")
        assert retry is not None
        assert retry.get_retries() == RedisMessagingSettings().retries == 3
        supported = set(retry._supported_errors)
        assert RedisConnectionError in supported
        assert RedisTimeoutError not in supported
    finally:
        await client.aclose()
        _client_cache.clear()


async def test_client_retries_setting_is_configurable(monkeypatch: pytest.MonkeyPatch):
    """The bounded retry count is driven by the PREFECT_REDIS_MESSAGING_RETRIES setting."""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_RETRIES", "1")
    _client_cache.clear()
    client = get_async_redis_client()
    try:
        assert client.connection_pool.connection_kwargs["retry"].get_retries() == 1
    finally:
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


async def test_clear_cached_clients_disconnects_and_closes_current_loop_clients():
    """clear_cached_clients reaps clients on the current loop and empties the cache."""
    _client_cache.clear()

    client = AsyncMock(spec=Redis)
    client.connection_pool = MagicMock()
    client.connection_pool.disconnect = AsyncMock()
    key = (get_async_redis_client, (), (), _running_loop())
    _client_cache[key] = client

    await clear_cached_clients()

    client.connection_pool.disconnect.assert_awaited_once_with(inuse_connections=True)
    client.aclose.assert_awaited_once()
    assert _client_cache == {}


async def test_clear_cached_clients_skips_other_loop_clients():
    """Clients bound to a different loop are left untouched (not awaited)."""
    _client_cache.clear()

    other_loop = asyncio.new_event_loop()
    try:
        client = AsyncMock(spec=Redis)
        client.connection_pool = MagicMock()
        client.connection_pool.disconnect = AsyncMock()
        key = (get_async_redis_client, (), (), other_loop)
        _client_cache[key] = client

        await clear_cached_clients()

        client.connection_pool.disconnect.assert_not_awaited()
        client.aclose.assert_not_awaited()
        # The other loop's entry is left in place; it can only be reaped safely
        # from its own loop.
        assert _client_cache.get(key) is client
    finally:
        _client_cache.clear()
        other_loop.close()


async def test_clear_cached_clients_preserves_concurrent_replacement():
    """A client cached for the same key while we await must survive (P1b race).

    clear_cached_clients detaches the entries it will close before the first
    await, then clears only that snapshot. A replacement inserted during the
    disconnect/close await is therefore kept open rather than dropped, which
    would otherwise orphan the freshly recovered pool.
    """
    _client_cache.clear()
    key = (get_async_redis_client, (), (), _running_loop())

    replacement = AsyncMock(spec=Redis)

    async def insert_replacement(*args: object, **kwargs: object) -> None:
        _client_cache[key] = replacement

    old = AsyncMock(spec=Redis)
    old.connection_pool = MagicMock()
    old.connection_pool.disconnect = AsyncMock(side_effect=insert_replacement)
    _client_cache[key] = old

    await clear_cached_clients()

    old.connection_pool.disconnect.assert_awaited_once_with(inuse_connections=True)
    old.aclose.assert_awaited_once()
    assert _client_cache.get(key) is replacement
    replacement.aclose.assert_not_awaited()
    _client_cache.clear()


class _BlackholeProxy:
    """A TCP proxy that can stop relaying traffic to simulate a network partition."""

    def __init__(self, upstream_host: str, upstream_port: int):
        self.upstream = (upstream_host, upstream_port)
        self.blackhole = asyncio.Event()
        self._server: asyncio.AbstractServer | None = None

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.sockets[0].getsockname()[1]

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _pump(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                while self.blackhole.is_set():
                    await asyncio.sleep(0.05)
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _handle(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(
                *self.upstream
            )
        except Exception:
            client_writer.close()
            return
        await asyncio.gather(
            self._pump(client_reader, upstream_writer),
            self._pump(upstream_reader, client_writer),
        )


@pytest.mark.parametrize("construction", ["host_port", "from_url"])
async def test_pool_recovers_after_outage(
    isolated_redis_db_number: int, construction: str
):
    """Regression test for OSS-8071 / #22478.

    With a non-None socket_timeout and a bounded retry policy, blocking reads
    against an unreachable broker raise promptly (rather than hanging forever or
    being retried ~10 times while holding the connection), so their connections
    are released instead of being stuck `in_use` and permanently exhausting the
    pool. The client must resume operating once the broker is reachable again
    without a process restart. Both the host/port `Redis(...)` path used in
    production and the `Redis.from_url` path are exercised.
    """
    settings = RedisMessagingSettings()
    proxy = _BlackholeProxy(settings.host, settings.port)
    await proxy.start()

    if construction == "host_port":
        client = get_async_redis_client(
            host="127.0.0.1",
            port=proxy.port,
            db=isolated_redis_db_number,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    else:
        client = get_async_redis_client(
            url=f"redis://127.0.0.1:{proxy.port}/{isolated_redis_db_number}",
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    try:
        await client.ping()
        pool = client.connection_pool

        # Broker becomes unreachable mid-read.
        proxy.blackhole.set()

        # Without a socket_timeout these blocking reads would hang forever,
        # leaving their connections stuck `in_use`. They must instead fail
        # fast so the connections are reaped.
        reads = [
            asyncio.create_task(client.xread({"oss8071:stream": "$"}, block=1000))
            for _ in range(5)
        ]
        results = await asyncio.gather(*reads, return_exceptions=True)
        assert all(isinstance(r, RedisError) for r in results)
        assert len(pool._in_use_connections) == 0

        # Broker recovers; operations resume without a process restart.
        proxy.blackhole.clear()
        assert await client.ping() is True
    finally:
        await client.aclose()
        await proxy.stop()
        _client_cache.clear()
