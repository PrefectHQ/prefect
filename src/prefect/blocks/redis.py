from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

try:
    import redis.asyncio as redis
except ImportError:
    raise ImportError(
        "`redis-py` must be installed to use the `RedisStorageContainer` block. "
        "You can install it with `pip install redis>=5.0.1"
    )

from pydantic import Field
from pydantic.types import SecretStr
from typing_extensions import Self

from prefect.filesystems import WritableFileSystem
from prefect.utilities.asyncutils import sync_compatible


class RedisStorageContainer(WritableFileSystem):
    """
    Block used to interact with Redis as a filesystem

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
        from prefect.blocks.redis import RedisStorageContainer

        block = RedisStorageContainer.from_host(
            host="myredishost.com", username="redis", password="SuperSecret")
        block.save("BLOCK_NAME")
        ```

        Create a new block from a connection string
        ```python
        from prefect.blocks.redis import RedisStorageContainer
        block = RedisStorageContainer.from_url(""redis://redis:SuperSecret@myredishost.com:6379")
        block.save("BLOCK_NAME")
        ```
    """

    _logo_url = "https://stprododpcmscdnendpoint.azureedge.net/assets/icons/redis.png"

    host: Optional[str] = Field(default=None, description="Redis hostname")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis DB index")
    username: Optional[SecretStr] = Field(default=None, description="Redis username")
    password: Optional[SecretStr] = Field(default=None, description="Redis password")
    connection_string: Optional[SecretStr] = Field(
        default=None, description="Redis connection string"
    )

    def block_initialization(self) -> None:
        if self.connection_string:
            return
        if not self.host:
            raise ValueError("Initialization error: 'host' is required but missing.")
        if self.username and not self.password:
            raise ValueError(
                "Initialization error: 'username' is provided, but 'password' is missing. Both are required."
            )

    @sync_compatible
    async def read_path(self, path: Union[Path, str]):
        """Read the redis content at `path`

        Args:
            path: Redis key to read from

        Returns:
            Contents at key as bytes
        """
        async with self._client() as client:
            return await client.get(str(path))

    @sync_compatible
    async def write_path(self, path: Union[Path, str], content: bytes):
        """Write `content` to the redis at `path`

        Args:
            path: Redis key to write to
            content: Binary object to write
        """

        async with self._client() as client:
            return await client.set(str(path), content)

    @asynccontextmanager
    async def _client(self) -> AsyncGenerator[redis.Redis, None]:
        if self.connection_string:
            client = redis.Redis.from_url(self.connection_string.get_secret_value())
        else:
            assert self.host
            client = redis.Redis(
                host=self.host,
                port=self.port,
                username=self.username.get_secret_value() if self.username else None,
                password=self.password.get_secret_value() if self.password else None,
                db=self.db,
            )

        try:
            yield client
        finally:
            await client.aclose()

    @classmethod
    def from_host(
        cls,
        host: str,
        port: int = 6379,
        db: int = 0,
        username: Union[None, str, SecretStr] = None,
        password: Union[None, str, SecretStr] = None,
    ) -> Self:
        """Create block from hostname, username and password

        Args:
            host: Redis hostname
            username: Redis username
            password: Redis password
            port: Redis port

        Returns:
            `RedisStorageContainer` instance
        """

        username = SecretStr(username) if isinstance(username, str) else username
        password = SecretStr(password) if isinstance(password, str) else password

        return cls(host=host, port=port, db=db, username=username, password=password)

    @classmethod
    def from_connection_string(cls, connection_string: Union[str, SecretStr]) -> Self:
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
            `RedisStorageContainer` instance
        """

        connection_string = (
            SecretStr(connection_string)
            if isinstance(connection_string, str)
            else connection_string
        )

        return cls(connection_string=connection_string)
