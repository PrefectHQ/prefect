"""Redis connection URL parsing and client construction.

This module centralizes how `prefect_redis` turns a connection URL into a Redis
client so that the messaging client, the lock manager, and the `RedisDatabase`
block all share a single parser and builder rather than each constructing a
`redis.Redis` from scalar host/port settings.

A `+sentinel` suffix on the scheme selects Sentinel discovery: the current master
is resolved through the listed Sentinel daemons via `Sentinel.master_for()` and
failover is followed automatically. A `rediss` prefix turns on TLS for the data
nodes. The grammar follows the `redis-sentinel-url` convention::

    redis://[user:pass@]host:port[/db][?params]
    rediss://[user:pass@]host:port[/db][?params]
    redis+sentinel://[user:pass@]host:port[,host2:port2,...]/service_name[/db][?params]
    rediss+sentinel://[user:pass@]host:port[,host2:port2,...]/service_name[/db][?params]

Ports are optional and default to 6379 for single-node URLs and 26379 (the
Sentinel convention) for Sentinel members.

The `sentinel_username` and `sentinel_password` query parameters configure
authentication to the Sentinel daemons separately from the data nodes. All other
query parameters are standard redis-py connection options (`socket_timeout`,
`max_connections`, `health_check_interval`, ...) and apply to the data-node
connections with exactly the same parsing as a standalone `redis://` URL.

The `redis+sentinel://` grammar and the Sentinel data-node TCP keepalive defaults
(`SENTINEL_SOCKET_KEEPALIVE_OPTIONS`) deliberately mirror docket's `_redis_sentinel`
module (https://github.com/chrisguidry/docket/pull/431). prefect connects to the
same Sentinel topologies as docket and needs sync clients as well, so it keeps its
own parser/builder rather than importing docket's currently-private async-only
helpers; matching the convention keeps the two convergent and makes adopting
docket's helpers a drop-in change if they are promoted to a public API.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any, Union
from urllib.parse import SplitResult, parse_qs, unquote, urlencode, urlsplit, urlunsplit

import redis
import redis.asyncio
from redis.asyncio.connection import parse_url as _redis_py_parse_url
from redis.asyncio.sentinel import Sentinel as AsyncSentinel
from redis.sentinel import Sentinel as SyncSentinel

# Connection URL schemes. A `+sentinel` suffix selects Sentinel discovery; a
# `rediss` prefix turns on TLS for the data nodes.
SCHEME_SENTINEL = frozenset({"redis+sentinel", "rediss+sentinel"})
SCHEME_TLS = frozenset({"rediss", "rediss+sentinel"})
SCHEME_ALL = frozenset({"redis", "rediss"}) | SCHEME_SENTINEL

_SECRET_QUERY_KEYS = frozenset({"password", "sentinel_password"})
_REDACTED = "***"
_DEFAULT_PORT = 6379
# Sentinel daemons listen on 26379 by default, so sentinel members without an
# explicit port assume that rather than the data-node port.
_DEFAULT_SENTINEL_PORT = 26379

# Tight TCP keepalive probes for the data-node (master) connections in Sentinel
# mode. A master that dies *silently* — a network partition or frozen host that
# never sends a FIN/RST — would otherwise leave a blocking read (e.g. the
# messaging client's XREADGROUP, which runs with no socket read timeout) waiting
# on the OS-default keepalive (~2 hours on Linux) while Sentinel completes
# failover in seconds. Pinning these probes means a dead peer is noticed in
# roughly TCP_KEEPIDLE + TCP_KEEPCNT * TCP_KEEPINTVL seconds. The probes only
# fire on an otherwise-idle socket and a healthy peer answers them, so they don't
# disturb a legitimately long blocking read. These match redis-py 8.0's own
# defaults; pinning them keeps behaviour identical on the older redis-py releases
# that default to no keepalive. This mirrors docket's `_redis_sentinel` module so
# the two stay convergent (see the module docstring).
_SENTINEL_KEEPALIVE_TIMERS: tuple[tuple[str, int], ...] = (
    ("TCP_KEEPIDLE", 30),
    ("TCP_KEEPINTVL", 5),
    ("TCP_KEEPCNT", 3),
)
SENTINEL_SOCKET_KEEPALIVE_OPTIONS: dict[int, int] = {
    int(getattr(socket, name)): value
    for name, value in _SENTINEL_KEEPALIVE_TIMERS
    if hasattr(socket, name)
}
# Applied to the data-node connections as defaults; URL query options and caller
# kwargs override them, just as a socket_keepalive in a standalone URL would win.
_SENTINEL_DATA_NODE_DEFAULTS: dict[str, Any] = {
    "socket_keepalive": True,
    "socket_keepalive_options": SENTINEL_SOCKET_KEEPALIVE_OPTIONS,
}


class RedisUrlError(ValueError):
    """Raised when a Redis connection URL cannot be parsed into a valid connection."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RedisConnectionConfig:
    """Validated description of a Redis connection parsed from a URL.

    `connection_kwargs` and `sentinel_kwargs` hold redis-py-native keys
    (`username`, `password`, `ssl`, `ssl_cert_reqs`, `ssl_check_hostname`,
    `ssl_ca_certs`) so a caller can splat them directly. In Sentinel mode
    `connection_kwargs` applies to the data-node (master) connections and
    `sentinel_kwargs` to the Sentinel daemons.
    """

    db: int
    is_sentinel: bool
    host: Union[str, None] = None
    port: Union[int, None] = None
    service_name: Union[str, None] = None
    sentinels: tuple[tuple[str, int], ...] = ()
    connection_kwargs: dict[str, Any] = field(default_factory=dict)
    sentinel_kwargs: dict[str, Any] = field(default_factory=dict)


def _split_connection_url(url: str) -> "tuple[SplitResult, str]":
    """Split a connection URL, tolerating multi-host netlocs with IPv6 members.

    Recent CPython releases reject netlocs like `s1:26379,[::1]:26379` with
    "Invalid IPv6 URL" because data precedes a bracket, so the netloc is carved
    off by hand and `urlsplit` parses the URL with a placeholder host instead.

    Returns:
        The parsed parts (scheme, path, query, fragment) and the raw netloc.
    """
    scheme, separator, remainder = url.partition("://")
    if not separator:
        return urlsplit(url), ""
    end = len(remainder)
    for terminator in "/?#":
        index = remainder.find(terminator)
        if index != -1:
            end = min(end, index)
    netloc, tail = remainder[:end], remainder[end:]
    return urlsplit(f"{scheme}://netloc-placeholder{tail}"), netloc


def is_sentinel_url(url: str) -> bool:
    """Return True if the URL uses a Redis Sentinel scheme.

    Splits the scheme off by hand rather than using `urlparse`: a Sentinel
    member list that includes an IPv6 host (e.g.
    `redis+sentinel://s1:26379,[::1]:26379/mymaster`) makes `urlparse` raise
    `ValueError: Invalid IPv6 URL` before the tolerant `parse_redis_url` path
    can run. Schemes are matched case-insensitively per RFC 3986.
    """
    return url.partition("://")[0].lower() in SCHEME_SENTINEL


def redact_redis_url(url: str) -> str:
    """Return `url` with the userinfo password and sensitive query values masked."""
    try:
        parts, netloc = _split_connection_url(url)
    except ValueError:
        return _REDACTED

    if "@" in netloc:
        userinfo, hostpart = netloc.rsplit("@", 1)
        if ":" in userinfo:
            user, _ = userinfo.split(":", 1)
            userinfo = f"{user}:{_REDACTED}"
        netloc = f"{userinfo}@{hostpart}"

    query = ""
    if parts.query:
        pairs: list[str] = []
        for key, values in parse_qs(parts.query, keep_blank_values=True).items():
            value = (
                _REDACTED
                if key in _SECRET_QUERY_KEYS
                else (values[0] if values else "")
            )
            pairs.append(f"{key}={value}")
        query = "&".join(pairs)

    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def _parse_db(segment: str, *, url: str) -> int:
    try:
        db = int(segment)
    except ValueError as exc:
        raise RedisUrlError(
            f"Invalid database index {segment!r} in connection URL: {redact_redis_url(url)}"
        ) from exc
    if db < 0:
        raise RedisUrlError(
            f"Database index {db} must be non-negative in connection URL: {redact_redis_url(url)}"
        )
    return db


def _split_members(
    hostpart: str, *, url: str, default_port: int = _DEFAULT_PORT
) -> list[tuple[str, int]]:
    """Split a comma-separated `host:port,host2:port2` netloc into members.

    `urlsplit` only exposes the segment before the first comma through
    `.hostname`/`.port`, so the multi-host netloc is split by hand.
    """
    members: list[tuple[str, int]] = []
    for raw_entry in hostpart.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        if entry.startswith("["):
            # Bracketed IPv6 member, e.g. [::1] or [::1]:26380
            host, _, rest = entry[1:].partition("]")
            port_str = rest.removeprefix(":") or str(default_port)
        else:
            host, separator, port_str = entry.rpartition(":")
            if not separator:
                host, port_str = entry, str(default_port)
        if not host:
            raise RedisUrlError(
                f"Missing host in connection URL: {redact_redis_url(url)}"
            )
        try:
            port = int(port_str)
        except ValueError as exc:
            raise RedisUrlError(
                f"Invalid port {port_str!r} in connection URL: {redact_redis_url(url)}"
            ) from exc
        members.append((host, port))
    if not members:
        raise RedisUrlError(f"No host found in connection URL: {redact_redis_url(url)}")
    return members


def _funnel_query_options(query: dict[str, list[str]], *, url: str) -> dict[str, Any]:
    """Convert leftover query parameters into redis-py connection options.

    The Sentinel-specific keys have been popped from `query` by this point;
    everything left is a standard redis-py connection option (`socket_timeout`,
    `max_connections`, `health_check_interval`, ...). Funnel them through
    redis-py's `parse_url` on a synthetic standalone URL so they get exactly the
    same type conversion and validation as a `redis://` URL, mirroring docket's
    `_redis_sentinel` parser (see the module docstring). The database comes from
    the path and credentials from the userinfo, so `db`/`username`/`password`
    are not allowed to sneak in through the query string.
    """
    if not query:
        return {}
    remaining = urlencode(
        [(name, value) for name, values in query.items() for value in values]
    )
    try:
        options: dict[str, Any] = _redis_py_parse_url(f"redis:///?{remaining}")
    except ValueError as exc:
        raise RedisUrlError(
            f"Invalid connection option in connection URL "
            f"({exc}): {redact_redis_url(url)}"
        ) from exc
    for governed in ("db", "username", "password"):
        options.pop(governed, None)
    return options


def parse_redis_url(url: str) -> RedisConnectionConfig:
    """Parse a Redis connection URL into a validated `RedisConnectionConfig`.

    Raises:
        RedisUrlError: With secrets redacted, for any unsupported scheme, malformed
            member list, missing Sentinel service name, negative database index, or
            malformed connection option.
    """
    parts, netloc = _split_connection_url(url)
    scheme = parts.scheme.lower()
    if scheme not in SCHEME_ALL:
        raise RedisUrlError(
            f"Unsupported scheme {parts.scheme!r} in connection URL: {redact_redis_url(url)}"
        )

    is_sentinel = scheme in SCHEME_SENTINEL
    tls = scheme in SCHEME_TLS

    userinfo = ""
    hostpart = netloc
    if "@" in netloc:
        userinfo, hostpart = netloc.rsplit("@", 1)

    username: Union[str, None] = None
    password: Union[str, None] = None
    if userinfo:
        if ":" in userinfo:
            raw_user, raw_password = userinfo.split(":", 1)
            username = unquote(raw_user) or None
            password = unquote(raw_password)
        else:
            username = unquote(userinfo) or None

    members = _split_members(
        hostpart,
        url=url,
        default_port=_DEFAULT_SENTINEL_PORT if is_sentinel else _DEFAULT_PORT,
    )
    path_segments = [segment for segment in parts.path.split("/") if segment]
    query = parse_qs(parts.query, keep_blank_values=True)

    connection_kwargs: dict[str, Any] = {}
    if username is not None:
        connection_kwargs["username"] = username
    if password is not None:
        connection_kwargs["password"] = password
    if tls:
        connection_kwargs["ssl"] = True

    if not is_sentinel:
        if len(members) > 1:
            raise RedisUrlError(
                f"Multiple hosts require a +sentinel scheme: {redact_redis_url(url)}"
            )
        db = _parse_db(path_segments[0], url=url) if path_segments else 0
        host, port = members[0]
        connection_kwargs.update(_funnel_query_options(query, url=url))
        return RedisConnectionConfig(
            db=db,
            is_sentinel=False,
            host=host,
            port=port,
            connection_kwargs=connection_kwargs,
        )

    if not path_segments:
        raise RedisUrlError(
            f"A Sentinel connection URL requires a service name: {redact_redis_url(url)}"
        )
    service_name = path_segments[0]
    db = _parse_db(path_segments[1], url=url) if len(path_segments) > 1 else 0

    sentinel_kwargs: dict[str, Any] = {}
    sentinel_username = query.pop("sentinel_username", [None])[0]
    sentinel_password = query.pop("sentinel_password", [None])[0]
    if sentinel_username:
        sentinel_kwargs["username"] = sentinel_username
    if sentinel_password:
        sentinel_kwargs["password"] = sentinel_password
    if tls:
        sentinel_kwargs["ssl"] = True
    connection_kwargs.update(_funnel_query_options(query, url=url))

    return RedisConnectionConfig(
        db=db,
        is_sentinel=True,
        service_name=service_name,
        sentinels=tuple(members),
        connection_kwargs=connection_kwargs,
        sentinel_kwargs=sentinel_kwargs,
    )


def build_redis_client(
    config: RedisConnectionConfig, *, asynchronous: bool, **extra: Any
) -> Union[redis.Redis, redis.asyncio.Redis]:
    """Build a Redis client from a parsed `RedisConnectionConfig`.

    When `config.is_sentinel` is set the current master is resolved through the
    Sentinel daemons and the returned client follows failover automatically.
    Otherwise a plain single-node client is returned.

    `extra` holds additional redis-py connection kwargs the caller wants applied to
    the data-node connection (e.g. `decode_responses` or `health_check_interval`).
    """
    if config.is_sentinel:
        assert config.service_name is not None  # guaranteed by parse_redis_url
        # Tight TCP keepalive is applied to the data-node (master) connections so
        # a silently-dead master is noticed promptly while Sentinel fails over
        # (see SENTINEL_SOCKET_KEEPALIVE_OPTIONS). Defaults go first so URL options
        # win, and `extra` (passed through master_for) overrides both. Keepalive is
        # deliberately not applied to the Sentinel daemon connections, which only
        # carry short discovery polls.
        data_node_kwargs = {**_SENTINEL_DATA_NODE_DEFAULTS, **config.connection_kwargs}
        # redis-py copies socket_* options from connection_kwargs into
        # sentinel_kwargs only when sentinel_kwargs is None; the explicit dict
        # always passed here suppresses that fallback. Forward the caller's
        # timeouts so a partitioned Sentinel daemon fails fast during master
        # discovery instead of blocking on OS connect defaults. Keepalive stays
        # data-node only: the daemon connections carry short discovery polls.
        sentinel_kwargs: dict[str, Any] = {
            key: extra[key]
            for key in ("socket_timeout", "socket_connect_timeout")
            if key in extra
        }
        sentinel_kwargs.update(config.sentinel_kwargs)
        if asynchronous:
            async_sentinel = AsyncSentinel(
                list(config.sentinels),
                sentinel_kwargs=sentinel_kwargs,
                **data_node_kwargs,
            )
            return async_sentinel.master_for(config.service_name, db=config.db, **extra)
        sync_sentinel = SyncSentinel(
            list(config.sentinels),
            sentinel_kwargs=sentinel_kwargs,
            **data_node_kwargs,
        )
        return sync_sentinel.master_for(config.service_name, db=config.db, **extra)

    redis_class = redis.asyncio.Redis if asynchronous else redis.Redis
    return redis_class(
        host=config.host,
        port=config.port,
        db=config.db,
        **{**config.connection_kwargs, **extra},
    )


def close_redis_client(client: redis.Redis) -> None:
    """Close a sync client returned by `build_redis_client`.

    A Sentinel-backed client holds one extra Redis client per Sentinel daemon
    on its connection pool's `sentinel_manager`; closing only the returned
    client would leave those daemon connections to be reclaimed by the garbage
    collector (emitting `ResourceWarning`s). This closes both.
    """
    client.close()
    manager = getattr(client.connection_pool, "sentinel_manager", None)
    if manager is not None:
        for daemon_client in manager.sentinels:
            daemon_client.close()


async def aclose_redis_client(client: redis.asyncio.Redis) -> None:
    """Async counterpart of `close_redis_client`."""
    await client.aclose()
    manager = getattr(client.connection_pool, "sentinel_manager", None)
    if manager is not None:
        for daemon_client in manager.sentinels:
            await daemon_client.aclose()
