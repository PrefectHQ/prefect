import asyncio
import functools
import warnings
from typing import Any, Callable, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import Field, model_validator
from redis.asyncio import Redis
from typing_extensions import Self, TypeAlias

from prefect.logging import get_logger
from prefect.settings.base import (
    PrefectBaseSettings,
    build_settings_config,  # type: ignore[reportPrivateUsage]
)

logger = get_logger(__name__)

_UNSET: Any = object()


class RedisMessagingSettings(PrefectBaseSettings):
    """Settings for connecting to Redis.

    Connection can be configured either via a single `url` field
    (e.g. `redis://user:pass@host:6379/0`) or with the individual
    `host`/`port`/`db`/… fields.  When `url` is set it takes
    precedence and the discrete fields are ignored.

    Environment variable: `PREFECT_REDIS_MESSAGING_URL`
    """

    model_config = build_settings_config(
        (
            "redis",
            "messaging",
        ),
        frozen=True,
    )

    url: Optional[str] = Field(
        default=None,
        description=(
            "Full Redis URL (e.g. redis://user:pass@host:6379/0 or "
            "rediss://… for TLS). When set, host/port/db/username/"
            "password/ssl are ignored."
        ),
    )
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    username: str = Field(default="default")
    password: str = Field(default="")
    health_check_interval: int = Field(
        default=20,
        description="Health check interval for pinging the server; defaults to 20 seconds.",
    )
    ssl: bool = Field(
        default=False,
        description="Whether to use SSL for the Redis connection",
    )
    socket_timeout: Optional[float] = Field(
        default=60.0,
        description=(
            "Timeout in seconds for socket read operations. None means no "
            "timeout. Consumers with a longer PREFECT_REDIS_MESSAGING_CONSUMER_BLOCK "
            "extend this automatically for their own client, so idle blocking "
            "reads (e.g. XREADGROUP) don't time out spuriously."
        ),
    )
    socket_connect_timeout: Optional[float] = Field(
        default=10.0,
        description=(
            "Timeout in seconds for socket connect operations. None means no timeout."
        ),
    )
    protocol: int = Field(
        default=2,
        description=(
            "RESP protocol version. Defaults to 2 for compatibility "
            "with older Redis servers and proxies."
        ),
    )

    _DISCRETE_FIELDS: frozenset[str] = frozenset(
        {"host", "port", "db", "username", "password", "ssl"}
    )

    @model_validator(mode="after")
    def _warn_url_overrides_discrete_fields(self) -> Self:
        conflicting = self._DISCRETE_FIELDS & self.model_fields_set
        if self.url is not None and conflicting:
            warnings.warn(
                f"Redis URL is set; the following fields are ignored: "
                f"{', '.join(sorted(conflicting))}",
            )
        return self


CacheKey: TypeAlias = tuple[
    Callable[..., Any],
    tuple[Any, ...],
    tuple[tuple[str, Any], ...],
    Union[asyncio.AbstractEventLoop, None],
]

_client_cache: dict[CacheKey, Redis] = {}


def is_cluster_url(url: str) -> bool:
    """Return True if the URL uses the Redis Cluster scheme."""
    return url.partition("://")[0] in {"redis+cluster", "rediss+cluster"}


def normalize_cluster_url(url: str) -> str:
    """Return a redis-py compatible URL for Redis Cluster connections."""
    parsed = urlparse(url)
    if parsed.scheme not in {"redis+cluster", "rediss+cluster"}:
        return url

    return urlunparse(parsed._replace(scheme=parsed.scheme.replace("+cluster", "")))


def url_socket_timeout(url: str) -> Optional[float]:
    """Return the `socket_timeout` query parameter of a Redis URL, if set.

    `Redis.from_url` gives querystring arguments precedence over keyword
    arguments, so this is the effective timeout regardless of what a caller
    passes alongside the URL.
    """
    values = parse_qs(urlparse(url).query).get("socket_timeout")
    return float(values[0]) if values else None


def with_socket_timeout(url: str, socket_timeout: float) -> str:
    """Return `url` with its `socket_timeout` query parameter set to `socket_timeout`."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["socket_timeout"] = [str(socket_timeout)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


@functools.cache
def _get_redis_messaging_url() -> str | None:
    return RedisMessagingSettings().url


def cluster_key_prefix(prefix: str, url: str | None = None) -> str:
    """Return a key prefix, hash-tagged when configured for Redis Cluster."""
    url = url or _get_redis_messaging_url()
    if url and is_cluster_url(url):
        return f"{{{prefix}}}"
    return prefix


def redis_key(prefix: str, suffix: str, url: str | None = None) -> str:
    """Return a Redis key rooted at a cluster-aware prefix."""
    return f"{cluster_key_prefix(prefix, url=url)}:{suffix}"


def _raise_cluster_not_supported() -> None:
    raise NotImplementedError(
        "Redis Cluster URLs are detected but not enabled yet. "
        "Cluster support requires hash-slot-safe keys across the Redis-backed "
        "messaging, ordering, lease storage, and cleanup queue subsystems."
    )


def _running_loop() -> Union[asyncio.AbstractEventLoop, None]:
    try:
        return asyncio.get_running_loop()
    except RuntimeError as e:
        if "no running event loop" in str(e):
            return None
        raise


def cached(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def cached_fn(*args: Any, **kwargs: Any) -> Redis:
        key = (fn, args, tuple(kwargs.items()), _running_loop())
        if key not in _client_cache:
            _client_cache[key] = fn(*args, **kwargs)
        return _client_cache[key]

    return cached_fn


def close_all_cached_connections() -> None:
    """Close all cached Redis connections."""
    loop: Union[asyncio.AbstractEventLoop, None]

    for (_, _, _, loop), client in _client_cache.items():
        if not loop or (loop and loop.is_closed()):
            continue
        loop.run_until_complete(client.connection_pool.disconnect())
        loop.run_until_complete(client.aclose())


async def clear_cached_clients(client: Union[Redis, None] = None) -> None:
    """Close and clear cached Redis clients and the messaging URL lookup.

    Without closing, connections stuck in-use from a hung operation are never
    released and the pool eventually exhausts its connection cap.

    Args:
        client: If given, only this cached client is closed and evicted;
            other cached clients (e.g. for other endpoints) are left running.
            If omitted, every current-loop client is closed.
    """
    _get_redis_messaging_url.cache_clear()

    current_loop = _running_loop()
    for key, cached_client in list(_client_cache.items()):
        if client is not None and cached_client is not client:
            continue
        _, _, _, loop = key
        if loop is not None and loop is not current_loop:
            continue  # can't await a client bound to another loop
        _client_cache.pop(key, None)
        try:
            await cached_client.aclose()
        except Exception:
            logger.exception("Error closing cached Redis client")


@cached
def get_async_redis_client(
    url: Union[str, None] = None,
    host: Union[str, None] = None,
    port: Union[int, None] = None,
    db: Union[int, None] = None,
    password: Union[str, None] = None,
    username: Union[str, None] = None,
    health_check_interval: Union[int, None] = None,
    decode_responses: bool = True,
    ssl: Union[bool, None] = None,
    socket_timeout: Union[float, None, Any] = _UNSET,
    socket_connect_timeout: Union[float, None, Any] = _UNSET,
    protocol: Union[int, None] = None,
) -> Redis:
    """Retrieves an async Redis client.

    When a standalone `url` is provided (or configured via
    `PREFECT_REDIS_MESSAGING_URL`), `Redis.from_url` is used and
    the discrete host/port/… arguments are ignored. Redis Cluster
    URLs are detected but intentionally not enabled yet.

    Args:
        url: Full Redis URL (e.g. `redis://localhost:6379/0`).
        host: The host location.
        port: The port to connect to the host with.
        db: The Redis database to interact with.
        password: The password for the redis host
        username: Username for the redis instance
        health_check_interval: Health check interval in seconds.
        decode_responses: Whether to decode binary responses from Redis to
            unicode strings.
        ssl: Whether to use SSL for the connection.
        socket_timeout: Timeout for socket read operations (None = no timeout).
        socket_connect_timeout: Timeout for socket connect (None = no timeout).
        protocol: RESP protocol version (default 2 from settings).

    Returns:
        Redis: a Redis client
    """
    settings = RedisMessagingSettings()

    resolved_socket_timeout = (
        settings.socket_timeout if socket_timeout is _UNSET else socket_timeout
    )
    resolved_socket_connect_timeout = (
        settings.socket_connect_timeout
        if socket_connect_timeout is _UNSET
        else socket_connect_timeout
    )
    resolved_protocol = protocol if protocol is not None else settings.protocol

    url = url or settings.url
    if url:
        if is_cluster_url(url):
            _raise_cluster_not_supported()
        return Redis.from_url(
            url,
            health_check_interval=(
                health_check_interval
                if health_check_interval is not None
                else settings.health_check_interval
            ),
            decode_responses=decode_responses,
            socket_timeout=resolved_socket_timeout,
            socket_connect_timeout=resolved_socket_connect_timeout,
            protocol=resolved_protocol,
        )

    return Redis(
        host=host or settings.host,
        port=port if port is not None else settings.port,
        db=db if db is not None else settings.db,
        password=password or settings.password,
        username=username or settings.username,
        health_check_interval=(
            health_check_interval
            if health_check_interval is not None
            else settings.health_check_interval
        ),
        ssl=ssl if ssl is not None else settings.ssl,
        decode_responses=decode_responses,
        socket_timeout=resolved_socket_timeout,
        socket_connect_timeout=resolved_socket_connect_timeout,
        protocol=resolved_protocol,
    )


@cached
def async_redis_from_settings(
    settings: RedisMessagingSettings, **options: Any
) -> Redis:
    options = {
        "decode_responses": True,
        "socket_timeout": settings.socket_timeout,
        "socket_connect_timeout": settings.socket_connect_timeout,
        "protocol": settings.protocol,
        **options,
    }

    if settings.url:
        if is_cluster_url(settings.url):
            _raise_cluster_not_supported()
        return Redis.from_url(
            settings.url,
            health_check_interval=settings.health_check_interval,
            **options,
        )

    return Redis(
        host=settings.host,
        port=settings.port,
        db=settings.db,
        password=settings.password,
        username=settings.username,
        health_check_interval=settings.health_check_interval,
        ssl=settings.ssl,
        **options,
    )
