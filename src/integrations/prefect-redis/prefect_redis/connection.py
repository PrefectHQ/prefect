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

Single-node URLs accept `tls_insecure` and `tls_ca_file` query parameters; the
Sentinel schemes additionally accept `sentinel_username`, `sentinel_password`,
`sentinel_ssl`, `sentinel_tls_insecure` and `sentinel_tls_ca_file` to configure
the connections to the Sentinel daemons separately from the data nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union
from urllib.parse import SplitResult, parse_qs, unquote, urlsplit, urlunsplit

import redis
import redis.asyncio
from redis.asyncio.sentinel import Sentinel as AsyncSentinel
from redis.sentinel import Sentinel as SyncSentinel

# Connection URL schemes. A `+sentinel` suffix selects Sentinel discovery; a
# `rediss` prefix turns on TLS for the data nodes.
SCHEME_SENTINEL = frozenset({"redis+sentinel", "rediss+sentinel"})
SCHEME_TLS = frozenset({"rediss", "rediss+sentinel"})
SCHEME_ALL = frozenset({"redis", "rediss"}) | SCHEME_SENTINEL

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_SECRET_QUERY_KEYS = frozenset({"password", "sentinel_password"})
_REDACTED = "***"
_DEFAULT_PORT = 6379
# Sentinel daemons listen on 26379 by default, so sentinel members without an
# explicit port assume that rather than the data-node port.
_DEFAULT_SENTINEL_PORT = 26379


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


def _to_bool(value: str, *, url: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise RedisUrlError(
        f"Invalid boolean value {value!r} in connection URL: {redact_redis_url(url)}"
    )


def _parse_db(segment: str, *, url: str) -> int:
    try:
        db = int(segment)
    except ValueError as exc:
        raise RedisUrlError(
            f"Invalid database index {segment!r} in connection URL: {redact_redis_url(url)}"
        ) from exc
    if not 0 <= db <= 15:
        raise RedisUrlError(
            f"Database index {db} out of range (0-15) in connection URL: {redact_redis_url(url)}"
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


def _build_ssl_kwargs(
    *, enabled: bool, query: dict[str, list[str]], url: str, prefix: str = ""
) -> dict[str, Any]:
    if not enabled:
        return {"ssl": False}
    insecure = _to_bool(query.get(f"{prefix}tls_insecure", ["false"])[0], url=url)
    return {
        "ssl": True,
        "ssl_cert_reqs": "none" if insecure else "optional",
        "ssl_check_hostname": not insecure,
        "ssl_ca_certs": query.get(f"{prefix}tls_ca_file", [None])[0],
    }


def parse_redis_url(url: str) -> RedisConnectionConfig:
    """Parse a Redis connection URL into a validated `RedisConnectionConfig`.

    Raises:
        RedisUrlError: With secrets redacted, for any unsupported scheme, malformed
            member list, missing Sentinel service name, or out-of-range database index.
    """
    parts, netloc = _split_connection_url(url)
    scheme = parts.scheme.lower()
    if scheme not in SCHEME_ALL:
        raise RedisUrlError(
            f"Unsupported scheme {parts.scheme!r} in connection URL: {redact_redis_url(url)}"
        )

    is_sentinel = scheme in SCHEME_SENTINEL
    tls_default = scheme in SCHEME_TLS

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
    connection_kwargs.update(
        _build_ssl_kwargs(enabled=tls_default, query=query, url=url)
    )

    if not is_sentinel:
        if len(members) > 1:
            raise RedisUrlError(
                f"Multiple hosts require a +sentinel scheme: {redact_redis_url(url)}"
            )
        db = _parse_db(path_segments[0], url=url) if path_segments else 0
        host, port = members[0]
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
    sentinel_username = query.get("sentinel_username", [None])[0]
    sentinel_password = query.get("sentinel_password", [None])[0]
    if sentinel_username:
        sentinel_kwargs["username"] = sentinel_username
    if sentinel_password:
        sentinel_kwargs["password"] = sentinel_password
    sentinel_ssl_raw = query.get("sentinel_ssl", [None])[0]
    sentinel_tls = (
        tls_default if sentinel_ssl_raw is None else _to_bool(sentinel_ssl_raw, url=url)
    )
    sentinel_kwargs.update(
        _build_ssl_kwargs(
            enabled=sentinel_tls, query=query, url=url, prefix="sentinel_"
        )
    )

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
        if asynchronous:
            async_sentinel = AsyncSentinel(
                list(config.sentinels),
                sentinel_kwargs=dict(config.sentinel_kwargs),
                **config.connection_kwargs,
            )
            return async_sentinel.master_for(config.service_name, db=config.db, **extra)
        sync_sentinel = SyncSentinel(
            list(config.sentinels),
            sentinel_kwargs=dict(config.sentinel_kwargs),
            **config.connection_kwargs,
        )
        return sync_sentinel.master_for(config.service_name, db=config.db, **extra)

    redis_class = redis.asyncio.Redis if asynchronous else redis.Redis
    return redis_class(
        host=config.host,
        port=config.port,
        db=config.db,
        **{**config.connection_kwargs, **extra},
    )


def redis_client_from_url(
    url: str, *, asynchronous: bool, **extra: Any
) -> Union[redis.Redis, redis.asyncio.Redis]:
    """Convenience wrapper: `build_redis_client(parse_redis_url(url), ...)`."""
    return build_redis_client(parse_redis_url(url), asynchronous=asynchronous, **extra)
