import asyncio
import functools
from typing import Any, Callable, Union

from pydantic import Field
from redis.asyncio import Redis
from typing_extensions import TypeAlias

from prefect.settings.base import (
    PrefectBaseSettings,
    build_settings_config,  # type: ignore[reportPrivateUsage]
)


class RedisMessagingSettings(PrefectBaseSettings):
    model_config = build_settings_config(
        (
            "redis",
            "messaging",
        ),
        frozen=True,
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


CacheKey: TypeAlias = tuple[
    Callable[..., Any],
    tuple[Any, ...],
    tuple[tuple[str, Any], ...],
    Union[asyncio.AbstractEventLoop, None],
]

_client_cache: dict[CacheKey, Redis] = {}


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


@cached
def get_async_redis_client(
    host: Union[str, None] = None,
    port: Union[int, None] = None,
    db: Union[int, None] = None,
    password: Union[str, None] = None,
    username: Union[str, None] = None,
    health_check_interval: Union[int, None] = None,
    decode_responses: bool = True,
    ssl: Union[bool, None] = None,
) -> Redis:
    """Retrieves an async Redis client.

    Args:
        host: The host location.
        port: The port to connect to the host with.
        db: The Redis database to interact with.
        password: The password for the redis host
        username: Username for the redis instance
        decode_responses: Whether to decode binary responses from Redis to
            unicode strings.

    Returns:
        Redis: a Redis client
    """
    settings = RedisMessagingSettings()

    return Redis(
        host=host or settings.host,
        port=port or settings.port,
        db=db or settings.db,
        password=password or settings.password,
        username=username or settings.username,
        health_check_interval=health_check_interval or settings.health_check_interval,
        ssl=ssl or settings.ssl,
        decode_responses=decode_responses,
    )


@cached
def async_redis_from_settings(
    settings: RedisMessagingSettings, **options: Any
) -> Redis:
    options = {
        "decode_responses": True,
        **options,
    }
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
