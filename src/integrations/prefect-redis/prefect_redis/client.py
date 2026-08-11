import asyncio
import functools
import warnings
from typing import Any, Callable, Optional, Union
from urllib.parse import urlparse, urlunparse

from pydantic import Field, model_validator
from redis.asyncio import Redis
from typing_extensions import Self, TypeAlias

from prefect.settings.base import (
    PrefectBaseSettings,
    build_settings_config,  # type: ignore[reportPrivateUsage]
)

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
        default=None,
        description=(
            "Timeout in seconds for socket read operations. "
            "None means no timeout (preserves pre-redis-py-8 behavior)."
        ),
    )
    socket_connect_timeout: Optional[float] = Field(
        default=None,
        description=(
            "Timeout in seconds for socket connect operations. "
            "None means no timeout (preserves pre-redis-py-8 behavior)."
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


def cluster_key_prefix(prefix: str, url: str | None = None) -> str:
    """Return a key prefix, hash-tagged when configured for Redis Cluster."""
    url = url or RedisMessagingSettings().url
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


def _close_dead_loop_client(client: Redis) -> None:
    """Release the sockets held by a client whose event loop is gone.

    ``Redis.aclose()`` cannot run once the client's event loop has closed, so
    the cached client's connection pool would otherwise keep its sockets
    ``ESTABLISHED`` until the process exits, leaking a file descriptor per
    orphaned loop. redis-py's own ``StreamWriter.close()`` also needs a running
    loop (see ``Connection.__del__``), so we instead close each connection's
    underlying socket directly, which frees the descriptor without touching the
    dead loop. Attribute access is defensive so a redis-py internals change
    degrades to a no-op rather than an error.
    """
    pool = getattr(client, "connection_pool", None)
    if pool is None:
        return

    connections = [
        *getattr(pool, "_available_connections", []),
        *getattr(pool, "_in_use_connections", set()),
    ]
    for connection in connections:
        writer = getattr(connection, "_writer", None)
        if writer is None:
            continue
        try:
            sock = writer.transport.get_extra_info("socket")
        except AttributeError:
            sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        # Drop the stream references so the connection is not reused and so
        # Connection.__del__ does not emit a spurious "unclosed Connection"
        # ResourceWarning for a socket we have already closed.
        connection._reader = connection._writer = None


def close_all_cached_connections() -> None:
    """Close every cached Redis client and empty the cache.

    Clients bound to an event loop that is still usable are closed with
    ``aclose()`` on that loop. Clients whose loop has already ended -- exactly
    the ones that would otherwise leak their file descriptors -- have their
    sockets closed directly, since ``aclose()`` cannot run on a dead loop. The
    cache is cleared afterwards so later calls return fresh clients.
    """
    loop: Union[asyncio.AbstractEventLoop, None]

    for (_, _, _, loop), client in list(_client_cache.items()):
        if loop is not None and not loop.is_closed():
            loop.run_until_complete(client.connection_pool.disconnect())
            loop.run_until_complete(client.aclose())
        else:
            _close_dead_loop_client(client)
    _client_cache.clear()


async def clear_cached_clients() -> None:
    """Close and clear all cached Redis clients to force fresh connections.

    This should be called when a connection error is detected to ensure
    subsequent calls to get_async_redis_client() return fresh clients
    rather than stale ones with broken connections. Each client is closed
    before the cache is cleared so its connection pool does not leak: the
    client on the running loop is awaited, clients whose loop has ended have
    their sockets closed directly, and a client on another live loop is closed
    on that loop without blocking this one.
    """
    global _client_cache

    running_loop = _running_loop()
    for (_, _, _, loop), client in list(_client_cache.items()):
        if running_loop is not None and loop is running_loop:
            try:
                await client.aclose()
            except Exception:
                _close_dead_loop_client(client)
        elif loop is None or loop.is_closed():
            _close_dead_loop_client(client)
        else:
            # Bound to a different, still-open loop: close it on its own loop
            # without blocking this one; fall back to a direct socket close.
            try:
                asyncio.run_coroutine_threadsafe(client.aclose(), loop)
            except Exception:
                _close_dead_loop_client(client)
    _client_cache.clear()


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
            health_check_interval=health_check_interval
            or settings.health_check_interval,
            decode_responses=decode_responses,
            socket_timeout=resolved_socket_timeout,
            socket_connect_timeout=resolved_socket_connect_timeout,
            protocol=resolved_protocol,
        )

    return Redis(
        host=host or settings.host,
        port=port or settings.port,
        db=db or settings.db,
        password=password or settings.password,
        username=username or settings.username,
        health_check_interval=health_check_interval or settings.health_check_interval,
        ssl=ssl or settings.ssl,
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
