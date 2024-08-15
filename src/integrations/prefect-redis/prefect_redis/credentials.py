"""Redis credentials handling"""

from typing import Optional, Union

import redis.asyncio as redis
from pydantic import Field
from pydantic.types import SecretStr

from prefect.filesystems import WritableFileSystem

DEFAULT_PORT = 6379


class RedisCredentials(WritableFileSystem):
    """
    Block used to manage authentication with Redis

    Attributes:
        host (str): The value to store.
        port (int): The value to store.
        db (int): The value to store.
        username (str): The value to store.
        password (str): The value to store.
        connection_string (str): The value to store.

    Example:
        Create a new block from hostname, username and password:
        ```python
        from prefect_redis import RedisBlock

        block = RedisBlock.from_host(
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

    _logo_url = "https://stprododpcmscdnendpoint.azureedge.net/assets/icons/redis.png"

    host: Optional[str] = Field(default=None, description="Redis hostname")
    port: int = Field(default=DEFAULT_PORT, description="Redis port")
    db: int = Field(default=0, description="Redis DB index")
    username: Optional[SecretStr] = Field(default=None, description="Redis username")
    password: Optional[SecretStr] = Field(default=None, description="Redis password")
    connection_string: Optional[SecretStr] = Field(
        default=None, description="Redis connection string"
    )

    def block_initialization(self) -> None:
        """Validate parameters"""

        if self.connection_string:
            return
        if not self.host:
            raise ValueError("Missing hostname")
        if self.username and not self.password:
            raise ValueError("Missing password")

    async def read_path(self, path: str) -> bytes:
        """Read a redis key

        Args:
            path: Redis key to read from

        Returns:
            Contents at key as bytes
        """
        client = self.get_client()
        ret = await client.get(path)

        await client.close()
        return ret

    async def write_path(self, path: str, content: bytes) -> None:
        """Write to a redis key

        Args:
            path: Redis key to write to
            content: Binary object to write
        """
        client = self.get_client()
        ret = await client.set(path, content)

        await client.close()
        return ret

    def get_client(self) -> redis.Redis:
        """Get Redis Client

        Returns:
            An initialized Redis async client
        """
        if self.connection_string:
            return redis.Redis.from_url(self.connection_string.get_secret_value())
        return redis.Redis(
            host=self.host,
            port=self.port,
            username=self.username.get_secret_value() if self.username else None,
            password=self.password.get_secret_value() if self.password else None,
            db=self.db,
        )

    @classmethod
    def from_host(
        cls,
        host: str,
        username: Union[None, str, SecretStr],
        password: Union[None, str, SecretStr],
        port: int = DEFAULT_PORT,
    ) -> "RedisCredentials":
        """Create block from hostname, username and password

        Args:
            host: Redis hostname
            username: Redis username
            password: Redis password
            port: Redis port

        Returns:
            `RedisCredentials` instance
        """
        return cls(host=host, username=username, password=password, port=port)

    @classmethod
    def from_connection_string(
        cls, connection_string: Union[str, SecretStr]
    ) -> "RedisCredentials":
        """Create block from a Redis connection string

        Supports the following URL schemes:
        - `redis://` creates a TCP socket connection
        - `rediss://` creates a SSL wrapped TCP socket connection
        - `unix://` creates a Unix Domain Socket connection

        See [Redis docs](https://redis.readthedocs.io/en/stable/examples
        /connection_examples.html#Connecting-to-Redis-instances-by-specifying-a-URL
        -scheme.) for more info.

        Args:
            connection_string: Redis connection string

        Returns:
            `RedisCredentials` instance
        """
        return cls(connection_string=connection_string)
