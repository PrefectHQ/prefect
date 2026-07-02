"""Tests that a connection URL (including Sentinel) flows through the messaging
client, the lock manager, and the `RedisDatabase` block.

These exercise client construction only; they do not require a live Sentinel
topology (building a Sentinel-backed client is lazy and does not connect).
"""

import pickle

import pytest
import redis
import redis.asyncio
from prefect_redis import client as client_module
from prefect_redis.blocks import RedisDatabase
from prefect_redis.client import (
    RedisMessagingSettings,
    async_redis_from_settings,
    get_async_redis_client,
    is_cluster_url,
    is_sentinel_url,
)
from prefect_redis.connection import RedisUrlError
from prefect_redis.locking import RedisLockManager
from redis.asyncio.sentinel import SentinelConnectionPool as AsyncSentinelPool
from redis.sentinel import SentinelConnectionPool as SyncSentinelPool

SENTINEL_URL = "redis+sentinel://s1:26379,s2:26379/mymaster/1"
# A Sentinel member list with an IPv6 host: `urlparse` rejects this netloc, so
# it is the regression case for scheme detection (see is_sentinel_url).
SENTINEL_URL_IPV6 = "redis+sentinel://s1:26379,[::1]:26379/mymaster"


# ---------------------------------------------------------------------------
# scheme detection (IPv6 member regression)
# ---------------------------------------------------------------------------


def test_is_sentinel_url_tolerates_ipv6_members() -> None:
    """Detection must not depend on urlparse, which raises on IPv6 netlocs."""
    assert is_sentinel_url(SENTINEL_URL_IPV6) is True
    assert is_sentinel_url("rediss+sentinel://[::1]:26379,s2:26379/svc") is True
    assert is_sentinel_url("redis://localhost:6379/0") is False
    assert is_sentinel_url("redis+cluster://localhost:6379") is False


def test_scheme_detection_is_case_insensitive() -> None:
    """RFC 3986 schemes are case-insensitive; parse_redis_url lowercases, so the
    dispatch predicates must too."""
    assert is_sentinel_url("Redis+Sentinel://s1:26379/mymaster") is True
    assert is_cluster_url("Redis+Cluster://localhost:6379") is True


def test_get_async_redis_client_accepts_ipv6_sentinel_url() -> None:
    """get_async_redis_client must build a Sentinel client for an IPv6 member list
    rather than raising `ValueError: Invalid IPv6 URL` before parsing."""
    client_module._client_cache.clear()
    try:
        client = get_async_redis_client(url=SENTINEL_URL_IPV6)
        assert isinstance(client.connection_pool, AsyncSentinelPool)
        assert client.connection_pool.service_name == "mymaster"
    finally:
        client_module._client_cache.clear()


# ---------------------------------------------------------------------------
# messaging client
# ---------------------------------------------------------------------------


def test_messaging_settings_sentinel_url_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", SENTINEL_URL)
    assert RedisMessagingSettings().url == SENTINEL_URL


async def test_async_redis_from_settings_sentinel_url() -> None:
    settings = RedisMessagingSettings(url=SENTINEL_URL)
    client = async_redis_from_settings(settings)
    assert isinstance(client.connection_pool, AsyncSentinelPool)
    assert client.connection_pool.service_name == "mymaster"
    # decode_responses defaulted by async_redis_from_settings is applied to the master
    assert client.connection_pool.connection_kwargs["decode_responses"] is True


async def test_get_async_redis_client_sentinel_url_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", SENTINEL_URL)
    # The no-arg client is cached globally; clear it so the URL branch is taken.
    client_module._client_cache.clear()
    try:
        client = get_async_redis_client()
        assert isinstance(client.connection_pool, AsyncSentinelPool)
        assert client.connection_pool.service_name == "mymaster"
    finally:
        client_module._client_cache.clear()


async def test_get_async_redis_client_sentinel_url_param() -> None:
    client_module._client_cache.clear()
    try:
        client = get_async_redis_client(url=SENTINEL_URL)
        assert isinstance(client.connection_pool, AsyncSentinelPool)
        assert client.connection_pool.service_name == "mymaster"
    finally:
        client_module._client_cache.clear()


async def test_get_async_redis_client_single_node_tls_query_params() -> None:
    """Single-node URLs carrying the documented tls_insecure/tls_ca_file params
    must be honored (redis-py's from_url would fail with a TypeError on them)."""
    client_module._client_cache.clear()
    try:
        client = get_async_redis_client(
            url="rediss://cache:6379/0?tls_insecure=true&tls_ca_file=/etc/ca.pem"
        )
        conn = client.connection_pool.connection_kwargs
        assert conn["ssl_cert_reqs"] == "none"
        assert conn["ssl_ca_certs"] == "/etc/ca.pem"
    finally:
        client_module._client_cache.clear()


async def test_async_redis_from_settings_single_node_tls_query_params() -> None:
    settings = RedisMessagingSettings(
        url="rediss://cache:6379/0?tls_insecure=true&tls_ca_file=/etc/ca.pem"
    )
    client = async_redis_from_settings(settings)
    conn = client.connection_pool.connection_kwargs
    assert conn["ssl_cert_reqs"] == "none"
    assert conn["ssl_ca_certs"] == "/etc/ca.pem"


async def test_get_async_redis_client_sentinel_url_wins_over_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured URL is authoritative; discrete host/port arguments are ignored."""
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", SENTINEL_URL)
    client_module._client_cache.clear()
    try:
        client = get_async_redis_client(host="explicit.host")
        assert isinstance(client.connection_pool, AsyncSentinelPool)
        assert client.connection_pool.service_name == "mymaster"
    finally:
        client_module._client_cache.clear()


# ---------------------------------------------------------------------------
# lock manager
# ---------------------------------------------------------------------------


def test_lock_manager_connection_url_builds_sentinel_clients() -> None:
    manager = RedisLockManager(connection_url=SENTINEL_URL)
    assert isinstance(manager.client, redis.Redis)
    assert isinstance(manager.async_client, redis.asyncio.Redis)
    assert isinstance(manager.client.connection_pool, SyncSentinelPool)
    assert isinstance(manager.async_client.connection_pool, AsyncSentinelPool)
    assert manager.client.connection_pool.service_name == "mymaster"


def test_lock_manager_connection_url_survives_pickling() -> None:
    manager = RedisLockManager(connection_url=SENTINEL_URL)
    restored = pickle.loads(pickle.dumps(manager))
    assert restored.connection_url == SENTINEL_URL
    assert isinstance(restored.client.connection_pool, SyncSentinelPool)
    assert isinstance(restored.async_client.connection_pool, AsyncSentinelPool)


def test_lock_manager_unpickles_pre_connection_url_state() -> None:
    """State dicts pickled by pre-connection_url prefect-redis versions lack the
    "connection_url" key; unpickling them must not raise AttributeError."""
    manager = RedisLockManager.__new__(RedisLockManager)
    manager.__setstate__(
        {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "username": None,
            "password": None,
            "ssl": False,
        }
    )
    assert manager.connection_url is None
    assert isinstance(manager.client, redis.Redis)
    assert isinstance(manager.async_client, redis.asyncio.Redis)


def test_lock_manager_without_url_uses_scalar_fields() -> None:
    manager = RedisLockManager(host="scalar.host", port=6390, db=4)
    assert not isinstance(manager.client.connection_pool, SyncSentinelPool)
    conn = manager.client.connection_pool.connection_kwargs
    assert conn["host"] == "scalar.host"
    assert conn["port"] == 6390
    assert conn["db"] == 4


# ---------------------------------------------------------------------------
# RedisDatabase block
# ---------------------------------------------------------------------------


def test_block_connection_url_builds_sentinel_clients() -> None:
    block = RedisDatabase(connection_url="redis+sentinel://s1:26379/mymaster")
    assert isinstance(block.get_client().connection_pool, SyncSentinelPool)
    assert isinstance(block.get_async_client().connection_pool, AsyncSentinelPool)


def test_block_invalid_connection_url_rejected() -> None:
    with pytest.raises(RedisUrlError, match="requires a service name"):
        RedisDatabase(connection_url="redis+sentinel://s1:26379")


def test_block_from_connection_string_sentinel() -> None:
    block = RedisDatabase.from_connection_string(
        "redis+sentinel://user:secret@s1:26379,s2:26379/mymaster"
    )
    assert block.connection_url is not None
    assert (
        block.connection_url.get_secret_value()
        == "redis+sentinel://user:secret@s1:26379,s2:26379/mymaster"
    )
    assert isinstance(block.get_async_client().connection_pool, AsyncSentinelPool)


def test_block_from_connection_string_single_node_unchanged() -> None:
    block = RedisDatabase.from_connection_string("redis://cache:6380/2")
    assert block.connection_url is None
    assert block.host == "cache"
    assert block.port == 6380
    assert block.db == 2


def test_block_from_connection_string_tolerates_ipv6_members() -> None:
    """Scheme detection must not crash on a Sentinel member list with an IPv6
    host (raw urlsplit raises `ValueError: Invalid IPv6 URL`)."""
    block = RedisDatabase.from_connection_string(SENTINEL_URL_IPV6)
    assert block.connection_url is not None
    assert block.connection_url.get_secret_value() == SENTINEL_URL_IPV6


def test_block_from_connection_string_retains_tls_query_params() -> None:
    """tls_insecure/tls_ca_file cannot be represented by the scalar fields, so
    URLs carrying them are stored verbatim instead of silently dropping them."""
    url = "rediss://cache:6379/0?tls_insecure=true&tls_ca_file=/etc/ca.pem"
    block = RedisDatabase.from_connection_string(url)
    assert block.connection_url is not None
    assert block.connection_url.get_secret_value() == url
    conn = block.get_client().connection_pool.connection_kwargs
    assert conn["ssl_cert_reqs"] == "none"
    assert conn["ssl_ca_certs"] == "/etc/ca.pem"


def test_block_as_connection_params_round_trips_into_lock_manager() -> None:
    block = RedisDatabase(connection_url=SENTINEL_URL)
    params = block.as_connection_params()
    assert params["connection_url"] == SENTINEL_URL
    manager = RedisLockManager(**params)
    assert manager.connection_url == SENTINEL_URL
    assert isinstance(manager.client.connection_pool, SyncSentinelPool)


def test_block_as_connection_params_omits_connection_url_when_unset() -> None:
    params = RedisDatabase(host="cache").as_connection_params()
    assert "connection_url" not in params
    assert params["host"] == "cache"
