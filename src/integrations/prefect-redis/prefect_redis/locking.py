from typing import Optional

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.lock import Lock as AsyncLock
from redis.lock import Lock

from prefect.locking.protocol import LockManager


class RedisLockManager(LockManager):
    """
    A lock manager that uses Redis as a backend.

    Attributes:
        host: The host of the Redis server
        port: The port the Redis server is running on
        db: The database to write to and read from
        username: The username to use when connecting to the Redis server
        password: The password to use when connecting to the Redis server
        ssl: Whether to use SSL when connecting to the Redis server
        client: The Redis client used to communicate with the Redis server
        async_client: The asynchronous Redis client used to communicate with the Redis server

    Example:
        Use with a cache policy:
        ```python
        from prefect import task
        from prefect.cache_policies import TASK_SOURCE, INPUTS
        from prefect.isolation_levels import SERIALIZABLE

        from prefect_redis import RedisLockManager

        cache_policy = (INPUTS + TASK_SOURCE).configure(
            isolation_level=SERIALIZABLE,
            lock_manager=RedisLockManager(host="my-redis-host"),
        )

        @task(cache_policy=cache_policy)
        def my_cached_task(x: int):
            return x + 42
        ```

        Configure with a `RedisDatabase` block:
        ```python
        from prefect_redis import RedisDatabase, RedisLockManager

        block = RedisDatabase(host="my-redis-host")
        lock_manager = RedisLockManager(**block.as_connection_params())
        ```
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.username = username
        self.password = password
        self.ssl = ssl
        self.client = Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            username=self.username,
            password=self.password,
        )
        self.async_client = AsyncRedis(
            host=self.host,
            port=self.port,
            db=self.db,
            username=self.username,
            password=self.password,
        )
        self._locks = {}

    @staticmethod
    def _lock_name_for_key(key: str) -> str:
        return f"lock:{key}"

    def acquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is not None and self.is_lock_holder(key, holder):
            return True
        else:
            lock = Lock(
                self.client, lock_name, timeout=hold_timeout, thread_local=False
            )
        lock_acquired = lock.acquire(token=holder, blocking_timeout=acquire_timeout)
        if lock_acquired:
            self._locks[lock_name] = lock
        return lock_acquired

    async def aacquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is not None and self.is_lock_holder(key, holder):
            return True
        else:
            lock = AsyncLock(
                self.async_client, lock_name, timeout=hold_timeout, thread_local=False
            )
        lock_acquired = await lock.acquire(
            token=holder, blocking_timeout=acquire_timeout
        )
        if lock_acquired:
            self._locks[lock_name] = lock
        return lock_acquired

    def release_lock(self, key: str, holder: str) -> None:
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is None or not self.is_lock_holder(key, holder):
            raise ValueError(f"No lock held by {holder} for transaction with key {key}")
        lock.release()
        del self._locks[lock_name]

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)
        lock_freed = lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            lock.release()
        return lock_freed

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = AsyncLock(self.async_client, lock_name)
        lock_freed = await lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            lock.release()
        return lock_freed

    def is_locked(self, key: str) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)
        return lock.locked()

    def is_lock_holder(self, key: str, holder: str) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        if (token := getattr(lock.local, "token", None)) is None:
            return False
        return token.decode() == holder
