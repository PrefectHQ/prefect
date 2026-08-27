"""Redis client construction from connection URLs, including Redis Sentinel.

redis-py already parses standalone `redis://` and `rediss://` URLs (`Redis.from_url`)
and handles Sentinel master discovery and failover (`redis.sentinel.Sentinel`), but
it has no URL form for a Sentinel topology. This module adds that one convention and
otherwise defers to redis-py::

    redis+sentinel://[user:pass@]host[:port][,host2[:port2],...]/service_name[/db][?options]
    rediss+sentinel://...    (TLS for both the data nodes and the Sentinel daemons)

Sentinel members default to port 26379. The `sentinel_username` and
`sentinel_password` options authenticate to the Sentinel daemons; every other option
is a standard redis-py URL option applied to the data-node connections with redis-py's
own parsing, and on a TLS scheme the `ssl_*` options are shared with the daemon
connections so one private CA covers the whole topology. The grammar is the one
docket accepts for `PREFECT_SERVER_DOCKET_URL`, so a single URL serves both.
"""

from __future__ import annotations

from typing import Any, Literal, overload
from urllib.parse import parse_qs, urlencode, urlsplit

import redis
import redis.asyncio
import redis.asyncio.sentinel
import redis.sentinel
from redis.connection import parse_url

SENTINEL_SCHEMES = frozenset({"redis+sentinel", "rediss+sentinel"})
# Sentinel daemons listen on 26379 by default, so members without an explicit
# port assume that rather than the data-node port.
_DEFAULT_SENTINEL_PORT = 26379


def is_sentinel_url(url: str) -> bool:
    """Return True if the URL uses a Redis Sentinel scheme.

    Only the scheme is inspected: `urlsplit` rejects a member list with an IPv6
    host (`redis+sentinel://s1:26379,[::1]:26379/mymaster`) as an invalid IPv6
    URL. Schemes are matched case-insensitively per RFC 3986.
    """
    return url.partition("://")[0].lower() in SENTINEL_SCHEMES


@overload
def redis_from_url(
    url: str, *, asynchronous: Literal[False] = ..., **kwargs: Any
) -> redis.Redis: ...


@overload
def redis_from_url(
    url: str, *, asynchronous: Literal[True], **kwargs: Any
) -> redis.asyncio.Redis: ...


def redis_from_url(
    url: str, *, asynchronous: bool = False, **kwargs: Any
) -> redis.Redis | redis.asyncio.Redis:
    """Build a Redis client from a connection URL.

    Standalone URLs are handed to `Redis.from_url` unchanged. Sentinel URLs
    resolve the current master through the listed Sentinel daemons, and the
    returned client follows failover automatically. In both cases `kwargs` are
    connection defaults that URL query options override, as with `Redis.from_url`.

    Building a client is lazy and opens no connection. Close it with
    `close_redis_client` / `aclose_redis_client` so a Sentinel-backed client's
    daemon connections are released too.

    Raises:
        ValueError: If the URL is malformed. Messages do not echo the URL, so
            credentials embedded in it are never leaked.
    """
    if not is_sentinel_url(url):
        redis_class = redis.asyncio.Redis if asynchronous else redis.Redis
        return redis_class.from_url(url, **kwargs)

    sentinels, service_name, sentinel_kwargs, url_options = _parse_sentinel_url(url)
    connection_kwargs = {**kwargs, **url_options}
    # redis-py copies the socket_* options to the daemon connections only when
    # sentinel_kwargs is None; the explicit dict carrying the daemons' auth/TLS
    # would suppress that, so apply the same fallback here.
    sentinel_kwargs = {
        **{k: v for k, v in connection_kwargs.items() if k.startswith("socket_")},
        **sentinel_kwargs,
    }
    sentinel_class = (
        redis.asyncio.sentinel.Sentinel if asynchronous else redis.sentinel.Sentinel
    )
    sentinel = sentinel_class(
        sentinels, sentinel_kwargs=sentinel_kwargs, **connection_kwargs
    )
    return sentinel.master_for(service_name)


def _parse_sentinel_url(
    url: str,
) -> tuple[list[tuple[str, int]], str, dict[str, Any], dict[str, Any]]:
    """Split a Sentinel URL into members, service name, daemon kwargs and data-node options.

    Only the Sentinel-specific parts are parsed here: the member list, the service
    name and the `sentinel_*` options. Credentials, the database index and every
    other option are rebuilt into a standalone URL and parsed by redis-py, so they
    get exactly the semantics of a `redis://` URL.
    """
    scheme, _, remainder = url.partition("://")
    # Carve the netloc off by hand: urlsplit rejects a multi-host netloc with an
    # IPv6 member ("Invalid IPv6 URL").
    netloc_end = min(
        [index for index in map(remainder.find, "/?#") if index != -1],
        default=len(remainder),
    )
    netloc, tail = remainder[:netloc_end], remainder[netloc_end:]
    userinfo, _, hostpart = netloc.rpartition("@")

    parts = urlsplit(f"redis://placeholder{tail}")
    segments = [segment for segment in parts.path.split("/") if segment]
    if not segments:
        raise ValueError(
            "A Sentinel connection URL requires a service name after the member "
            "list, e.g. redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster"
        )
    service_name = segments[0]
    db_path = f"/{segments[1]}" if len(segments) > 1 else ""

    query = parse_qs(parts.query, keep_blank_values=True)
    sentinel_kwargs: dict[str, Any] = {}
    for option in ("username", "password"):
        values = query.pop(f"sentinel_{option}", [])
        if values and values[0]:
            sentinel_kwargs[option] = values[0]

    tls = scheme.lower() == "rediss+sentinel"
    authority = f"{userinfo}@placeholder" if userinfo else "placeholder"
    options = parse_url(
        f"{'rediss' if tls else 'redis'}://{authority}{db_path}"
        f"?{urlencode(query, doseq=True)}"
    )
    options.pop("host")
    if tls:
        # Sentinel pools select their TLS connection class from `ssl`, not from
        # the `connection_class` redis-py resolved for the standalone URL.
        options.pop("connection_class")
        options["ssl"] = True
        # The daemons share the data nodes' TLS profile: without this a private
        # CA passed as ?ssl_ca_certs= would apply to the master connections only
        # and every daemon connection would fail certificate verification.
        sentinel_kwargs["ssl"] = True
        sentinel_kwargs.update(
            {key: value for key, value in options.items() if key.startswith("ssl_")}
        )
    return _split_members(hostpart), service_name, sentinel_kwargs, options


def _split_members(hostpart: str) -> list[tuple[str, int]]:
    """Split a comma-separated `host[:port]` list into `(host, port)` Sentinel members.

    IPv6 hosts must be bracketed, e.g. `[::1]:26379`.
    """
    members: list[tuple[str, int]] = []
    for entry in hostpart.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if entry.startswith("["):
            host, _, rest = entry[1:].partition("]")
            port_text = rest.removeprefix(":")
        else:
            host, separator, port_text = entry.rpartition(":")
            if not separator:
                host, port_text = entry, ""
        if not host:
            raise ValueError("A Sentinel member is missing a host in connection URL")
        try:
            port = int(port_text) if port_text else _DEFAULT_SENTINEL_PORT
        except ValueError as exc:
            raise ValueError(
                f"Invalid port for Sentinel member {host!r} in connection URL"
            ) from exc
        members.append((host, port))
    if not members:
        raise ValueError(
            "A Sentinel connection URL requires at least one Sentinel member, "
            "e.g. redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster"
        )
    return members


def close_redis_client(client: redis.Redis) -> None:
    """Close a sync client returned by `redis_from_url`.

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
