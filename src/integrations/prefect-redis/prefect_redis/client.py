import asyncio
import functools
import socket
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


def _force_close_client_sockets(
    client: Redis, only_dead_loop_connections: bool = False
) -> None:
    """Synchronously close the sockets held by a client's connection pool.

    A client's connections are bound to the event loop that created them, so
    once that loop is closed there is no public async API able to release them
    (`connection_pool.disconnect()` / `client.aclose()` are coroutines that
    require a live, matching loop). This reaches the underlying socket through
    the asyncio transport and closes the file descriptor directly. The transport
    and connection-pool attributes accessed here are redis-py/asyncio internals,
    so every access is guarded — a non-standard pool (e.g. a cluster pool) is
    skipped rather than raising.

    Sockets must only be force-closed once their owning loop is already closed:
    that loop's selector is gone, so closing the raw file descriptor cannot
    race with a live transport still polling it. Force-closing a socket that
    belongs to a running loop would free the fd for reuse while asyncio still
    has it registered, corrupting an unrelated connection. Callers that know
    the client's owning loop is closed may close everything; for clients cached
    with no owning loop (created outside any loop, connections bound to
    whichever loop first awaited them), pass `only_dead_loop_connections=True`
    to close only connections whose own writer loop has closed.
    """
    pool = getattr(client, "connection_pool", None)
    if pool is None:
        return

    connections = list(getattr(pool, "_available_connections", [])) + list(
        getattr(pool, "_in_use_connections", [])
    )
    for conn in connections:
        writer = getattr(conn, "_writer", None)
        if writer is None:
            continue
        if only_dead_loop_connections and not _is_closed_loop(
            getattr(writer, "_loop", None)
        ):
            continue
        sock = _transport_socket(getattr(writer, "transport", None))
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        conn._writer = None
        conn._reader = None


def _transport_socket(transport: Any) -> Union[socket.socket, None]:
    """Return the raw, closeable socket behind an asyncio transport, if any.

    A selector transport owns the socket directly as `_sock`. A TLS transport
    (`rediss://` / `ssl=True`) has no `_sock`; it wraps a lower-level selector
    transport reached via `_ssl_protocol._transport`, which is what actually
    holds the fd. `get_extra_info("socket")` is deliberately avoided: it returns
    an `asyncio.TransportSocket` wrapper that forbids `close()`, so it cannot be
    used to release the fd. The walk is bounded to guard against cycles.

    Non-CPython transports (e.g. uvloop's) expose no `_sock`, so this returns
    None and the force-close path degrades to dropping the reference: the fd is
    then released when the garbage collector reclaims the orphaned pool rather
    than deterministically.
    """
    seen: set[int] = set()
    while transport is not None and id(transport) not in seen:
        seen.add(id(transport))
        sock = getattr(transport, "_sock", None)
        if sock is not None:
            return sock
        transport = getattr(
            getattr(transport, "_ssl_protocol", None), "_transport", None
        )
    return None


def _is_closed_loop(loop: Union[asyncio.AbstractEventLoop, None]) -> bool:
    return loop is not None and loop.is_closed()


def _evict_closed_loop_clients() -> None:
    """Drop and release cached clients whose owning event loop has closed.

    Keeps `_client_cache` bounded to roughly one entry per currently-live loop
    and releases the sockets those closed-loop clients would otherwise leak.
    """
    for key in list(_client_cache):
        if _is_closed_loop(key[3]):
            client = _client_cache.pop(key, None)
            if client is not None:
                _force_close_client_sockets(client)


def cached(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def cached_fn(*args: Any, **kwargs: Any) -> Redis:
        _evict_closed_loop_clients()
        key = (fn, args, tuple(kwargs.items()), _running_loop())
        if key not in _client_cache:
            _client_cache[key] = fn(*args, **kwargs)
        return _client_cache[key]

    return cached_fn


def close_all_cached_connections() -> None:
    """Close all cached Redis connections and clear the cache.

    Clients whose owning loop is still open are disconnected on that loop;
    clients whose loop has already closed have their sockets force-closed
    synchronously so their file descriptors are released. Clients that were
    never bound to a loop have their connections inspected individually:
    connections whose own loop has closed are force-closed, while connections
    on a still-running loop are left alone and dropped with the cache entry.
    """
    loop: Union[asyncio.AbstractEventLoop, None]

    for (_, _, _, loop), client in _client_cache.items():
        if _is_closed_loop(loop):
            _force_close_client_sockets(client)
        elif loop is None:
            _force_close_client_sockets(client, only_dead_loop_connections=True)
        else:
            loop.run_until_complete(client.connection_pool.disconnect())
            loop.run_until_complete(client.aclose())

    _client_cache.clear()


async def clear_cached_clients() -> None:
    """Clear all cached Redis clients to force fresh connections.

    This should be called when a connection error is detected to ensure
    subsequent calls to get_async_redis_client() return fresh clients
    rather than stale ones with broken connections. Clients bound to an
    already-closed loop have their sockets force-closed synchronously so their
    file descriptors are released rather than leaked; clients cached with no
    owning loop have only their dead-loop connections force-closed; all other
    clients are dropped from the cache without touching their live sockets
    (the caller replaces them with fresh clients on the next call).
    """
    global _client_cache

    for (_, _, _, loop), client in _client_cache.items():
        if _is_closed_loop(loop):
            _force_close_client_sockets(client)
        elif loop is None:
            _force_close_client_sockets(client, only_dead_loop_connections=True)

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
