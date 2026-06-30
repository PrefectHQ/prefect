from dataclasses import dataclass

import pytest
import redis
import redis.asyncio
from prefect_redis.connection import (
    SENTINEL_SOCKET_KEEPALIVE_OPTIONS,
    RedisConnectionConfig,
    RedisUrlError,
    build_redis_client,
    parse_redis_url,
    redact_redis_url,
    redis_client_from_url,
)
from redis.asyncio.sentinel import SentinelConnectionPool as AsyncSentinelPool
from redis.sentinel import SentinelConnectionPool as SyncSentinelPool

# ---------------------------------------------------------------------------
# parse_redis_url
# ---------------------------------------------------------------------------


@dataclass
class ParseCase:
    name: str
    url: str
    expected: RedisConnectionConfig


PARSE_CASES = [
    ParseCase(
        name="single_node_minimal",
        url="redis://localhost:6379/0",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="localhost",
            port=6379,
            connection_kwargs={"ssl": False},
        ),
    ),
    ParseCase(
        name="single_node_default_port_and_db",
        url="redis://cache",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={"ssl": False},
        ),
    ),
    ParseCase(
        name="single_node_tls_with_auth_and_encoded_password",
        url="rediss://user:pa%40ss@cache:6380/2",
        expected=RedisConnectionConfig(
            db=2,
            is_sentinel=False,
            host="cache",
            port=6380,
            connection_kwargs={
                "username": "user",
                "password": "pa@ss",
                "ssl": True,
                "ssl_cert_reqs": "optional",
                "ssl_check_hostname": True,
                "ssl_ca_certs": None,
            },
        ),
    ),
    ParseCase(
        name="single_node_username_only",
        url="redis://user@cache:6379",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={"username": "user", "ssl": False},
        ),
    ),
    ParseCase(
        name="single_node_tls_insecure_and_ca_file",
        url="rediss://cache:6379?tls_insecure=true&tls_ca_file=/etc/ca.pem",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={
                "ssl": True,
                "ssl_cert_reqs": "none",
                "ssl_check_hostname": False,
                "ssl_ca_certs": "/etc/ca.pem",
            },
        ),
    ),
    ParseCase(
        name="sentinel_multi_member_with_data_and_sentinel_auth",
        url="redis+sentinel://app:secret@s1:26379,s2:26379,s3:26379/mymaster/1"
        "?sentinel_username=su&sentinel_password=sp",
        expected=RedisConnectionConfig(
            db=1,
            is_sentinel=True,
            service_name="mymaster",
            sentinels=(("s1", 26379), ("s2", 26379), ("s3", 26379)),
            connection_kwargs={"username": "app", "password": "secret", "ssl": False},
            sentinel_kwargs={"username": "su", "password": "sp", "ssl": False},
        ),
    ),
    ParseCase(
        name="sentinel_members_default_to_sentinel_port",
        url="redis+sentinel://s1,s2:26380,[::1]/mymaster",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="mymaster",
            sentinels=(("s1", 26379), ("s2", 26380), ("::1", 26379)),
            connection_kwargs={"ssl": False},
            sentinel_kwargs={"ssl": False},
        ),
    ),
    ParseCase(
        name="sentinel_tls_data_nodes_follows_scheme",
        url="rediss+sentinel://s1:26379/svc",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379),),
            connection_kwargs={
                "ssl": True,
                "ssl_cert_reqs": "optional",
                "ssl_check_hostname": True,
                "ssl_ca_certs": None,
            },
            sentinel_kwargs={
                "ssl": True,
                "ssl_cert_reqs": "optional",
                "ssl_check_hostname": True,
                "ssl_ca_certs": None,
            },
        ),
    ),
    ParseCase(
        name="sentinel_ssl_override_disables_daemon_tls",
        url="rediss+sentinel://s1:26379/svc?tls_insecure=true&sentinel_ssl=false",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379),),
            connection_kwargs={
                "ssl": True,
                "ssl_cert_reqs": "none",
                "ssl_check_hostname": False,
                "ssl_ca_certs": None,
            },
            sentinel_kwargs={"ssl": False},
        ),
    ),
]


@pytest.mark.parametrize("case", PARSE_CASES, ids=lambda case: case.name)
def test_parse_redis_url(case: ParseCase) -> None:
    assert parse_redis_url(case.url) == case.expected


@dataclass
class ErrorCase:
    name: str
    url: str
    match: str


ERROR_CASES = [
    ErrorCase(
        name="unknown_scheme", url="http://cache:6379", match="Unsupported scheme"
    ),
    ErrorCase(
        name="sentinel_without_service",
        url="redis+sentinel://s1:26379",
        match="requires a service name",
    ),
    ErrorCase(
        name="multiple_hosts_without_sentinel",
        url="redis://h1:6379,h2:6379",
        match="require a \\+sentinel",
    ),
    ErrorCase(name="invalid_port", url="redis://cache:notaport", match="Invalid port"),
    ErrorCase(
        name="db_out_of_range", url="redis://cache:6379/99", match="out of range"
    ),
    ErrorCase(
        name="invalid_db", url="redis://cache:6379/abc", match="Invalid database index"
    ),
    ErrorCase(name="no_host", url="redis://", match="No host found"),
    ErrorCase(
        name="invalid_bool",
        url="rediss://cache:6379?tls_insecure=maybe",
        match="Invalid boolean",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=lambda case: case.name)
def test_parse_redis_url_errors(case: ErrorCase) -> None:
    with pytest.raises(RedisUrlError, match=case.match):
        parse_redis_url(case.url)


def test_redis_url_error_is_value_error() -> None:
    # Useful so callers (e.g. block validators) can treat it as a ValueError.
    assert issubclass(RedisUrlError, ValueError)


# ---------------------------------------------------------------------------
# redact_redis_url
# ---------------------------------------------------------------------------


@dataclass
class RedactCase:
    name: str
    url: str
    expected: str


REDACT_CASES = [
    RedactCase(
        name="no_secret_unchanged",
        url="redis://cache:6379/0",
        expected="redis://cache:6379/0",
    ),
    RedactCase(
        name="userinfo_password_masked",
        url="redis://app:secret@cache:6379/0",
        expected="redis://app:***@cache:6379/0",
    ),
    RedactCase(
        name="username_only_kept",
        url="redis://app@cache:6379/0",
        expected="redis://app@cache:6379/0",
    ),
    RedactCase(
        name="sensitive_query_params_masked",
        url="redis+sentinel://app:secret@s1:26379/mymaster?sentinel_password=sp&sentinel_username=su",
        expected="redis+sentinel://app:***@s1:26379/mymaster?sentinel_password=***&sentinel_username=su",
    ),
]


@pytest.mark.parametrize("case", REDACT_CASES, ids=lambda case: case.name)
def test_redact_redis_url(case: RedactCase) -> None:
    assert redact_redis_url(case.url) == case.expected


@dataclass
class NoLeakCase:
    name: str
    url: str
    secret: str


NO_LEAK_CASES = [
    NoLeakCase(
        name="sentinel_no_service",
        url="redis+sentinel://u:topsecret@s1:26379",
        secret="topsecret",
    ),
    NoLeakCase(
        name="bad_port", url="redis://u:topsecret@cache:nope", secret="topsecret"
    ),
    NoLeakCase(
        name="bad_bool",
        url="rediss://u:topsecret@cache:6379?tls_insecure=maybe",
        secret="topsecret",
    ),
]


@pytest.mark.parametrize("case", NO_LEAK_CASES, ids=lambda case: case.name)
def test_parse_redis_url_errors_redact_secrets(case: NoLeakCase) -> None:
    with pytest.raises(RedisUrlError) as exc_info:
        parse_redis_url(case.url)
    assert case.secret not in str(exc_info.value)


def test_connection_config_is_frozen() -> None:
    config = RedisConnectionConfig(db=0, is_sentinel=False, host="cache", port=6379)
    with pytest.raises(AttributeError):
        config.host = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_redis_client
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("asynchronous", [False, True])
def test_build_single_node_client(asynchronous: bool) -> None:
    client = build_redis_client(
        parse_redis_url("redis://cache:6380/3"), asynchronous=asynchronous
    )
    expected_type = redis.asyncio.Redis if asynchronous else redis.Redis
    assert isinstance(client, expected_type)
    conn = client.connection_pool.connection_kwargs
    assert conn["host"] == "cache"
    assert conn["port"] == 6380
    assert conn["db"] == 3


@pytest.mark.parametrize("asynchronous", [False, True])
def test_build_sentinel_client_discovers_master(asynchronous: bool) -> None:
    client = build_redis_client(
        parse_redis_url("redis+sentinel://s1:26379,s2:26379/mymaster/1"),
        asynchronous=asynchronous,
    )
    expected_type = redis.asyncio.Redis if asynchronous else redis.Redis
    expected_pool = AsyncSentinelPool if asynchronous else SyncSentinelPool
    assert isinstance(client, expected_type)
    pool = client.connection_pool
    assert isinstance(pool, expected_pool)
    assert pool.service_name == "mymaster"
    assert pool.is_master is True
    assert pool.connection_kwargs["db"] == 1
    sentinel_hosts = [
        (
            s.connection_pool.connection_kwargs["host"],
            s.connection_pool.connection_kwargs["port"],
        )
        for s in pool.sentinel_manager.sentinels
    ]
    assert sentinel_hosts == [("s1", 26379), ("s2", 26379)]


def test_build_client_passes_extra_kwargs_to_data_connection() -> None:
    client = build_redis_client(
        parse_redis_url("redis://cache:6379/0"),
        asynchronous=True,
        decode_responses=True,
        health_check_interval=42,
    )
    conn = client.connection_pool.connection_kwargs
    assert conn["decode_responses"] is True
    assert conn["health_check_interval"] == 42


def test_redis_client_from_url_helper() -> None:
    client = redis_client_from_url("redis://cache:6379/0", asynchronous=True)
    assert isinstance(client, redis.asyncio.Redis)


# ---------------------------------------------------------------------------
# Sentinel data-node TCP keepalive (mirrors docket's _redis_sentinel defaults)
# ---------------------------------------------------------------------------


def test_keepalive_options_match_expected_timers() -> None:
    # 30s idle, 5s interval, 3 probes — names guarded for platforms that lack
    # them, so the dict holds only the constants this OS actually defines.
    assert SENTINEL_SOCKET_KEEPALIVE_OPTIONS
    assert all(
        isinstance(option, int) and isinstance(value, int)
        for option, value in SENTINEL_SOCKET_KEEPALIVE_OPTIONS.items()
    )


# redis-py 8 already defaults socket_keepalive to True, while the redis 6/7
# releases prefect also supports default to no keepalive. So the version-stable
# signal that our pinned timers were applied is the explicit options dict, not
# the bool: only the Sentinel data-node connections carry our exact options.


@pytest.mark.parametrize("asynchronous", [False, True])
def test_sentinel_data_node_gets_keepalive_defaults(asynchronous: bool) -> None:
    client = build_redis_client(
        parse_redis_url("redis+sentinel://s1:26379,s2:26379/mymaster/1"),
        asynchronous=asynchronous,
    )
    conn = client.connection_pool.connection_kwargs
    assert conn["socket_keepalive"] is True
    assert conn["socket_keepalive_options"] == SENTINEL_SOCKET_KEEPALIVE_OPTIONS


@pytest.mark.parametrize("asynchronous", [False, True])
def test_sentinel_daemon_connections_have_no_pinned_keepalive(
    asynchronous: bool,
) -> None:
    # Keepalive is pinned only on the long-lived data-node connections, not on
    # the short discovery polls to the Sentinel daemons.
    client = build_redis_client(
        parse_redis_url("redis+sentinel://s1:26379/mymaster"),
        asynchronous=asynchronous,
    )
    sentinel_manager = client.connection_pool.sentinel_manager
    for sentinel in sentinel_manager.sentinels:
        conn = sentinel.connection_pool.connection_kwargs
        assert conn.get("socket_keepalive_options") != SENTINEL_SOCKET_KEEPALIVE_OPTIONS


@pytest.mark.parametrize("asynchronous", [False, True])
def test_single_node_has_no_pinned_keepalive(asynchronous: bool) -> None:
    client = build_redis_client(
        parse_redis_url("redis://cache:6379/0"), asynchronous=asynchronous
    )
    conn = client.connection_pool.connection_kwargs
    assert conn.get("socket_keepalive_options") != SENTINEL_SOCKET_KEEPALIVE_OPTIONS


@pytest.mark.parametrize("asynchronous", [False, True])
def test_caller_kwargs_override_keepalive_defaults(asynchronous: bool) -> None:
    # The pinned defaults go in first, so a caller (or URL) can still turn
    # keepalive off; this overrides the True our builder would otherwise set.
    client = build_redis_client(
        parse_redis_url("redis+sentinel://s1:26379/mymaster"),
        asynchronous=asynchronous,
        socket_keepalive=False,
    )
    assert client.connection_pool.connection_kwargs["socket_keepalive"] is False
