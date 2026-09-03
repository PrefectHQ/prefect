"""Tests for `redis_from_url`, the single URL-to-client factory in `prefect_redis`.

Standalone URLs are delegated to redis-py's `Redis.from_url`; Sentinel URLs build a
Sentinel-backed client. The assertions inspect the resulting client and connection
pool only. Building a client is lazy and opens no connection, so no Redis or
Sentinel topology is required.
"""

from unittest import mock

import pytest
import redis
import redis.asyncio
from prefect_redis.connection import (
    aclose_redis_client,
    close_redis_client,
    redis_from_url,
)
from redis.asyncio.connection import Connection as AsyncConnection
from redis.asyncio.connection import SSLConnection as AsyncSSLConnection
from redis.asyncio.sentinel import SentinelConnectionPool as AsyncSentinelPool
from redis.asyncio.sentinel import SentinelManagedConnection as AsyncSentinelManaged
from redis.asyncio.sentinel import (
    SentinelManagedSSLConnection as AsyncSentinelManagedSSL,
)
from redis.connection import Connection, SSLConnection
from redis.sentinel import SentinelConnectionPool as SyncSentinelPool
from redis.sentinel import SentinelManagedConnection, SentinelManagedSSLConnection

SENTINEL_URL = "redis+sentinel://s1:26379,s2:26379/mymaster"

sync_and_async = pytest.mark.parametrize(
    "asynchronous", [False, True], ids=["sync", "async"]
)


def daemons(client: redis.Redis | redis.asyncio.Redis) -> list[redis.Redis]:
    return list(client.connection_pool.sentinel_manager.sentinels)


def daemon_addresses(
    client: redis.Redis | redis.asyncio.Redis,
) -> list[tuple[str, int]]:
    return [
        (
            daemon.connection_pool.connection_kwargs["host"],
            daemon.connection_pool.connection_kwargs["port"],
        )
        for daemon in daemons(client)
    ]


# ---------------------------------------------------------------------------
# standalone URLs are redis-py's business
# ---------------------------------------------------------------------------


@sync_and_async
def test_standalone_url_is_delegated_to_redis_py(asynchronous: bool) -> None:
    url = "rediss://user:pa%40ss@cache:6380/2?socket_timeout=2.5"
    redis_class = redis.asyncio.Redis if asynchronous else redis.Redis
    with mock.patch.object(
        redis_class, "from_url", wraps=redis_class.from_url
    ) as from_url:
        client = redis_from_url(url, asynchronous=asynchronous, decode_responses=True)
    from_url.assert_called_once_with(url, decode_responses=True)

    assert isinstance(client, redis_class)
    assert not isinstance(client.connection_pool, (SyncSentinelPool, AsyncSentinelPool))
    assert client.connection_pool.connection_class is (
        AsyncSSLConnection if asynchronous else SSLConnection
    )
    conn = client.connection_pool.connection_kwargs
    assert (conn["host"], conn["port"], conn["db"]) == ("cache", 6380, 2)
    assert (conn["username"], conn["password"]) == ("user", "pa@ss")
    assert conn["socket_timeout"] == 2.5
    assert conn["decode_responses"] is True


# ---------------------------------------------------------------------------
# Sentinel URLs
# ---------------------------------------------------------------------------


@sync_and_async
def test_sentinel_url_builds_a_master_client(asynchronous: bool) -> None:
    client = redis_from_url(f"{SENTINEL_URL}/1", asynchronous=asynchronous)
    assert isinstance(client, redis.asyncio.Redis if asynchronous else redis.Redis)
    pool = client.connection_pool
    assert isinstance(pool, AsyncSentinelPool if asynchronous else SyncSentinelPool)
    assert pool.service_name == "mymaster"
    assert pool.is_master is True
    assert pool.connection_kwargs["db"] == 1
    assert pool.connection_class is (
        AsyncSentinelManaged if asynchronous else SentinelManagedConnection
    )
    assert daemon_addresses(client) == [("s1", 26379), ("s2", 26379)]
    for daemon in daemons(client):
        assert daemon.connection_pool.connection_class is (
            AsyncConnection if asynchronous else Connection
        )
        assert daemon.connection_pool.connection_kwargs.get("username") is None
        assert daemon.connection_pool.connection_kwargs.get("password") is None


@pytest.mark.parametrize(
    ("path", "db"),
    [
        pytest.param("/mymaster", 0, id="no_db"),
        pytest.param("/mymaster/", 0, id="trailing_slash"),
        pytest.param("/mymaster/3", 3, id="db"),
        pytest.param("/mymaster/3/", 3, id="db_trailing_slash"),
    ],
)
def test_sentinel_path_is_service_name_then_database(path: str, db: int) -> None:
    client = redis_from_url(f"redis+sentinel://s1:26379{path}")
    pool = client.connection_pool
    assert pool.service_name == "mymaster"
    assert pool.connection_kwargs.get("db", 0) == db


@sync_and_async
def test_sentinel_members_default_to_the_sentinel_port(asynchronous: bool) -> None:
    client = redis_from_url(
        "redis+sentinel://s1,s2:26380,[::1],[::2]:26381/mymaster",
        asynchronous=asynchronous,
    )
    assert daemon_addresses(client) == [
        ("s1", 26379),
        ("s2", 26380),
        ("::1", 26379),
        ("::2", 26381),
    ]


@sync_and_async
def test_sentinel_scheme_is_case_insensitive(asynchronous: bool) -> None:
    client = redis_from_url("Redis+Sentinel://s1/mymaster", asynchronous=asynchronous)
    assert isinstance(
        client.connection_pool, AsyncSentinelPool if asynchronous else SyncSentinelPool
    )
    tls_client = redis_from_url(
        "RedisS+Sentinel://s1/mymaster", asynchronous=asynchronous
    )
    assert tls_client.connection_pool.connection_class is (
        AsyncSentinelManagedSSL if asynchronous else SentinelManagedSSLConnection
    )


@sync_and_async
def test_data_node_and_daemon_credentials_are_separate(asynchronous: bool) -> None:
    client = redis_from_url(
        "redis+sentinel://app:pa%40ss@s1:26379/mymaster"
        "?sentinel_username=su&sentinel_password=sp",
        asynchronous=asynchronous,
    )
    conn = client.connection_pool.connection_kwargs
    # Userinfo is decoded by redis-py, exactly as in a standalone URL.
    assert (conn["username"], conn["password"]) == ("app", "pa@ss")
    for daemon in daemons(client):
        daemon_conn = daemon.connection_pool.connection_kwargs
        assert (daemon_conn["username"], daemon_conn["password"]) == ("su", "sp")
    # The daemon-only options must not leak into the data-node connections.
    assert "sentinel_username" not in conn
    assert "sentinel_password" not in conn


@sync_and_async
def test_tls_scheme_covers_data_nodes_and_daemons(asynchronous: bool) -> None:
    client = redis_from_url(
        "rediss+sentinel://s1:26379/mymaster"
        "?ssl_ca_certs=/etc/ca.pem&ssl_check_hostname=false",
        asynchronous=asynchronous,
    )
    pool = client.connection_pool
    assert pool.connection_class is (
        AsyncSentinelManagedSSL if asynchronous else SentinelManagedSSLConnection
    )
    assert pool.connection_kwargs["ssl_ca_certs"] == "/etc/ca.pem"
    assert pool.connection_kwargs["ssl_check_hostname"] is False
    # Without this a private CA would apply to the master connections only and
    # every daemon connection would fail certificate verification at discovery.
    for daemon in daemons(client):
        assert daemon.connection_pool.connection_class is (
            AsyncSSLConnection if asynchronous else SSLConnection
        )
        assert daemon.connection_pool.connection_kwargs["ssl_ca_certs"] == "/etc/ca.pem"
        assert daemon.connection_pool.connection_kwargs["ssl_check_hostname"] is False


@sync_and_async
def test_sentinel_query_options_use_redis_py_parsing(asynchronous: bool) -> None:
    client = redis_from_url(
        f"{SENTINEL_URL}?socket_timeout=2.5&health_check_interval=30"
        "&max_connections=10&protocol=3",
        asynchronous=asynchronous,
    )
    pool = client.connection_pool
    assert pool.connection_kwargs["socket_timeout"] == 2.5
    assert pool.connection_kwargs["health_check_interval"] == 30
    assert pool.connection_kwargs["protocol"] == 3
    # Pool-level options reach the pool rather than the connections.
    assert pool.max_connections == 10


@sync_and_async
@pytest.mark.parametrize(
    "url",
    ["redis://cache:6379/0", SENTINEL_URL],
    ids=["standalone", "sentinel"],
)
def test_url_options_override_caller_defaults(asynchronous: bool, url: str) -> None:
    # Callers pass settings-derived defaults; an explicit URL option must win over
    # them for Sentinel URLs exactly as it does for `Redis.from_url`.
    client = redis_from_url(
        f"{url}?socket_timeout=7&protocol=3",
        asynchronous=asynchronous,
        socket_timeout=None,
        protocol=2,
        decode_responses=True,
    )
    conn = client.connection_pool.connection_kwargs
    assert conn["socket_timeout"] == 7.0
    assert conn["protocol"] == 3
    # Defaults the URL does not mention still apply.
    assert conn["decode_responses"] is True


@sync_and_async
def test_daemons_inherit_socket_options_like_redis_py(asynchronous: bool) -> None:
    # redis-py only copies socket_* options into sentinel_kwargs when none are
    # given; the factory always passes daemon kwargs, so it must apply the same
    # fallback itself for a partitioned daemon to fail fast during discovery.
    client = redis_from_url(
        f"{SENTINEL_URL}?socket_timeout=2",
        asynchronous=asynchronous,
        socket_timeout=1.5,
        socket_connect_timeout=0.25,
    )
    assert client.connection_pool.connection_kwargs["socket_timeout"] == 2.0
    for daemon in daemons(client):
        conn = daemon.connection_pool.connection_kwargs
        assert conn["socket_timeout"] == 2.0
        assert conn["socket_connect_timeout"] == 0.25


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "match"),
    [
        pytest.param(
            "redis+sentinel://s1:26379", "requires a service name", id="no_service"
        ),
        pytest.param(
            "redis+sentinel:///mymaster",
            "at least one Sentinel member",
            id="no_members",
        ),
        pytest.param(
            "redis+sentinel://s1:notaport/mymaster", "Invalid port", id="bad_port"
        ),
        pytest.param(
            "redis+sentinel://:26379/mymaster", "missing a host", id="no_host"
        ),
        pytest.param(
            "redis+sentinel://s1:26379/mymaster/abc",
            "Invalid database index 'abc'",
            id="bad_db",
        ),
        pytest.param(
            "redis+sentinel://s1:26379/mymaster/1/2",
            "unexpected segments after the database index",
            id="extra_path_segments",
        ),
        pytest.param(
            "redis+sentinel://s1:26379/mymaster?socket_timeout=abc",
            "Invalid value for 'socket_timeout'",
            id="bad_option_is_rejected_by_redis_py",
        ),
        pytest.param(
            "http://cache:6379",
            "must specify one of the following schemes",
            id="unknown_scheme_is_rejected_by_redis_py",
        ),
    ],
)
def test_malformed_urls_raise_value_error(url: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        redis_from_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "redis+sentinel://u:topsecret@s1:26379",
        "redis+sentinel://u:topsecret@s1:26379/mymaster?socket_timeout=maybe",
        "redis+sentinel://u:topsecret@s1:26379/mymaster/abc",
        "redis+sentinel://u:topsecret@s1:26379/mymaster?sentinel_password=topsecret&protocol=x",
        "rediss://u:topsecret@cache:6379?socket_timeout=maybe",
    ],
)
def test_errors_do_not_leak_credentials(url: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        redis_from_url(url)
    assert "topsecret" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


def test_close_redis_client_closes_sentinel_daemons() -> None:
    client = redis_from_url(SENTINEL_URL)
    expected = [client, *daemons(client)]
    with mock.patch.object(redis.Redis, "close", autospec=True) as mock_close:
        close_redis_client(client)
    closed = [call.args[0] for call in mock_close.call_args_list]
    assert closed == expected


async def test_aclose_redis_client_closes_sentinel_daemons() -> None:
    client = redis_from_url(SENTINEL_URL, asynchronous=True)
    expected = [client, *daemons(client)]
    with mock.patch.object(redis.asyncio.Redis, "aclose", autospec=True) as mock_close:
        await aclose_redis_client(client)
    closed = [call.args[0] for call in mock_close.call_args_list]
    assert closed == expected


def test_close_redis_client_standalone() -> None:
    # No sentinel manager on the pool; the helper must not raise.
    close_redis_client(redis_from_url("redis://cache:6379/0"))


async def test_aclose_redis_client_standalone() -> None:
    await aclose_redis_client(redis_from_url("redis://cache:6379/0", asynchronous=True))
