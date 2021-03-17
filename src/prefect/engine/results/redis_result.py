import os
from typing import Any, TYPE_CHECKING
from prefect.engine.result import Result


if TYPE_CHECKING:
    import redis


class RedisResult(Result):
    """
    Hook for storing and retrieving constant Python objects in redis.

    connection_string: Redis URI used for Redis.from_url
        default to REDIS_STORAGE_CONNECTION_STRING
    ttl_seconds: key time to live in seconds if the result is to expire

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self, connection_string: str = None, ttl_seconds: int = None, **kwargs: Any
    ) -> None:
        self.connection_string = connection_string or os.getenv(
            "REDIS_STORAGE_CONNECTION_STRING"
        )
        self.ttl_seconds = ttl_seconds
        super().__init__(**kwargs)

    def initialize_redis_client(self) -> None:
        import redis

        self._redis_client = redis.Redis.from_url(self.connection_string)
        try:
            self._redis_client.ping()
        except (ConnectionError, redis.InvalidResponse) as ee:
            raise Exception(f"redis .. details .. {ee}")

    @property
    def redis_client(self) -> "redis.client.Redis":
        if not hasattr(self, "_redis_client"):
            self.initialize_redis_client()
        return self._redis_client

    @redis_client.setter
    def redis_client(self, val: Any) -> None:
        self._redis_client = val

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "_redis_client" in state:
            del state["_redis_client"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def read(self, location: str) -> Result:
        """
        Read from reids and deserialize the value at location

        Args:
            - location (str): Redis key
        """
        new = self.copy()
        new.location = location
        content = self.redis_client.get(new.location)
        new.value = new.serializer.deserialize(content)
        return new

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Write the value into location

        Args:
            - value_ (Any): value to be stored
            - **kwargs (optional): unused, for interface compatibility
        """
        new = self.format(**kwargs)
        new.value = value_
        binary_data = new.serializer.serialize(new.value)
        self.redis_client.set(new.location, binary_data, ex=self.ttl_seconds)
        return new

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Check existence of a key in redis.
        Args:
             - location (str): The redis key.
             - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: True, confirming the constant exists.
        """
        return self.redis_client.exists(location) != 0
