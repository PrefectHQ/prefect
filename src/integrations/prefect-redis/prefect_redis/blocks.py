"""Redis credentials handling"""

from typing import Any, Dict, Optional, Union, cast

import redis
import redis.asyncio
from pydantic import Field
from pydantic.types import SecretStr
from redis.asyncio.connection import parse_url

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.filesystems import WritableFileSystem
from prefect_redis.connection import (
    aclose_redis_client,
    build_redis_client,
    close_redis_client,
    is_sentinel_url,
    parse_redis_url,
)

DEFAULT_PORT = 6379


class RedisDatabase(WritableFileSystem):
    """
    Block used to manage authentication with a Redis database

    Attributes:
        host: The host of the Redis server
        port: The port the Redis server is running on
        db: The database to write to and read from
        username: The username to use when connecting to the Redis server
        password: The password to use when connecting to the Redis server
        ssl: Whether to use SSL when connecting to the Redis server
        key_ttl: Optional per-key TTL in seconds applied to every written key
            (`SET ... EX`); `None` (default) means keys never expire

    Example:
        Create a new block from hostname, username and password:
            ```python
            from prefect_redis import RedisDatabase

            block = RedisDatabase(
                host="myredishost.com", username="redis", password="SuperSecret")
            block.save("BLOCK_NAME")
            ```

        Create a new block from a connection string
            ```python
            from prefect_redis import RedisBlock
            block = RedisBlock.from_url(""redis://redis:SuperSecret@myredishost.com:6379")
            block.save("BLOCK_NAME")
            ```

        Get Redis client in order to interact directly with Redis
            ```python
            from prefect_redis import RedisBlock
            block = RedisBlock.load("BLOCK_NAME")
            redis_client = block.get_client()
            ```
    """

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/dfb02cfce09ce3ca88fea097659a83554dd7a850-596x512.png"
    _block_type_name = "Redis Database"

    host: str = Field(default="localhost", description="Redis hostname")
    port: int = Field(default=DEFAULT_PORT, description="Redis port")
    db: int = Field(default=0, description="Redis DB index")
    username: Optional[SecretStr] = Field(default=None, description="Redis username")
    password: Optional[SecretStr] = Field(default=None, description="Redis password")
    ssl: bool = Field(default=False, description="Whether to use SSL")
    key_ttl: Optional[int] = Field(
        default=None,
        gt=0,
        description=(
            "Optional per-key time-to-live in seconds, applied to every written "
            "key (Redis `SET ... EX`). Must be positive; when `None` (the "
            "default) keys never expire. Useful when using the block as "
            "`result_storage`/cache on a Redis with a `maxmemory` + "
            "`volatile-lru` eviction policy."
        ),
    )
    connection_url: Optional[SecretStr] = Field(
        default=None,
        description=(
            "Full Redis connection URL, authoritative over the scalar connection fields "
            "when set. Supports the redis://, rediss://, redis+sentinel:// and "
            "rediss+sentinel:// schemes; the Sentinel schemes resolve the current master "
            "through the listed Sentinel daemons and follow failover automatically, e.g. "
            "redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster."
        ),
    )

    def block_initialization(self) -> None:
        """Validate parameters"""

        if self.connection_url is not None:
            # Fail fast on a malformed URL rather than at first connection.
            parse_redis_url(self.connection_url.get_secret_value())
            return
        if not self.host:
            raise ValueError("Missing hostname")
        if self.username and not self.password:
            raise ValueError("Missing password")

    async def aread_path(self, path: str) -> bytes:
        """Read a redis key

        Args:
            path: Redis key to read from

        Returns:
            Contents at key as bytes

        Examples:
            Read a key:
                ```python
                content = await block.aread_path("my-key")
                ```
        """
        client = self.get_async_client()
        try:
            return await client.get(path)
        finally:
            await aclose_redis_client(client)

    @async_dispatch(aread_path)
    def read_path(self, path: str) -> bytes:
        """Read a redis key

        Args:
            path: Redis key to read from

        Returns:
            Contents at key as bytes

        Examples:
            Read a key:
                ```python
                content = block.read_path("my-key")
                ```
        """
        client = self.get_client()
        try:
            return client.get(path)
        finally:
            close_redis_client(client)

    async def awrite_path(self, path: str, content: bytes) -> bool:
        """Write to a redis key

        Args:
            path: Redis key to write to
            content: Binary object to write

        Examples:
            Write a key:
                ```python
                await block.awrite_path("my-key", b"contents")
                ```
        """
        client = self.get_async_client()
        try:
            return await client.set(path, content, ex=self.key_ttl) is True
        finally:
            await aclose_redis_client(client)

    @async_dispatch(awrite_path)
    def write_path(self, path: str, content: bytes) -> bool:
        """Write to a redis key

        Args:
            path: Redis key to write to
            content: Binary object to write

        Examples:
            Write a key:
                ```python
                block.write_path("my-key", b"contents")
                ```
        """
        client = self.get_client()
        try:
            return client.set(path, content, ex=self.key_ttl) is True
        finally:
            close_redis_client(client)

    def get_client(self) -> redis.Redis:
        """Get Redis Client

        Returns:
            An initialized Redis client
        """
        if self.connection_url is not None:
            return cast(
                redis.Redis,
                build_redis_client(
                    parse_redis_url(self.connection_url.get_secret_value()),
                    asynchronous=False,
                ),
            )
        return redis.Redis(
            host=self.host,
            port=self.port,
            username=self.username.get_secret_value() if self.username else None,
            password=self.password.get_secret_value() if self.password else None,
            db=self.db,
            ssl=self.ssl,
        )

    def get_async_client(self) -> redis.asyncio.Redis:
        """Get Redis Client

        Returns:
            An initialized Redis async client
        """
        if self.connection_url is not None:
            return cast(
                redis.asyncio.Redis,
                build_redis_client(
                    parse_redis_url(self.connection_url.get_secret_value()),
                    asynchronous=True,
                ),
            )
        return redis.asyncio.Redis(
            host=self.host,
            port=self.port,
            username=self.username.get_secret_value() if self.username else None,
            password=self.password.get_secret_value() if self.password else None,
            db=self.db,
            ssl=self.ssl,
        )

    @classmethod
    def from_connection_string(
        cls, connection_string: Union[str, SecretStr]
    ) -> "RedisDatabase":
        """Create block from a Redis connection string

        Supports the following URL schemes:
        - `redis://` creates a TCP socket connection
        - `rediss://` creates a SSL wrapped TCP socket connection
        - `redis+sentinel://` / `rediss+sentinel://` discover the master through
          Redis Sentinel and follow failover automatically

        Sentinel URLs are stored verbatim on `connection_url`; other URLs are
        flattened to the scalar host/port/db/username/password/ssl fields.

        Args:
            connection_string: Redis connection string

        Returns:
            `RedisDatabase` instance
        """
        raw_connection_string = (
            connection_string
            if isinstance(connection_string, str)
            else connection_string.get_secret_value()
        )

        # Sentinel URLs cannot be flattened to scalar host/port fields, so they are
        # retained verbatim and resolved through the Sentinel daemons at connect time.
        if is_sentinel_url(raw_connection_string):
            return cls(connection_url=SecretStr(raw_connection_string))

        connection_kwargs = parse_url(raw_connection_string)
        ssl = connection_kwargs.get("connection_class") == redis.asyncio.SSLConnection
        return cls(
            host=connection_kwargs.get("host", "localhost"),
            port=connection_kwargs.get("port", DEFAULT_PORT),
            db=connection_kwargs.get("db", 0),
            username=connection_kwargs.get("username"),
            password=connection_kwargs.get("password"),
            ssl=ssl,
        )

    def as_connection_params(self) -> Dict[str, Any]:
        """
        Return a dictionary suitable for unpacking
        """
        data = self.model_dump()
        data.pop("block_type_slug", None)
        # `key_ttl` governs write behavior, not the connection — never a client kwarg.
        data.pop("key_ttl", None)
        # Unwrap SecretStr fields
        if self.username is not None:
            data["username"] = self.username.get_secret_value()
        else:
            data.pop("username", None)

        if self.password is not None:
            data["password"] = self.password.get_secret_value()
        else:
            data.pop("password", None)

        if self.connection_url is not None:
            data["connection_url"] = self.connection_url.get_secret_value()
        else:
            data.pop("connection_url", None)

        return data
