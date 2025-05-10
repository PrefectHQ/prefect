from typing import Any, Optional

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
        # client and async_client are initialized lazily

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
        self.client: Optional[Redis] = None
        self.async_client: Optional[AsyncRedis] = None
        self._locks: dict[str, Lock | AsyncLock] = {}

    # ---------- pickle helpers ----------
    def __getstate__(self) -> dict[str, Any]:
        return {
            k: getattr(self, k)
            for k in ("host", "port", "db", "username", "password", "ssl")
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self.client = None
        self.async_client = None
        self._locks = {}

    # ------------------------------------

    def _ensure_clients(self) -> None:
        if self.client is None:
            self.client = Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ssl=self.ssl,
            )
        if self.async_client is None:
            self.async_client = AsyncRedis(
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ssl=self.ssl,
            )

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
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and self.is_lock_holder(
            key, holder
        ):  # is_lock_holder will also call _ensure_clients
            return True
        else:
            # If lock is None, or not held by current holder, create/acquire new one.
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
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and isinstance(lock, AsyncLock):
            if await lock.owned() and lock.local.token == holder.encode():
                return True
            else:
                lock = None

        if lock is None:
            assert self.async_client is not None, "Async client should be initialized"
            new_lock = AsyncLock(
                self.async_client, lock_name, timeout=hold_timeout, thread_local=False
            )
            lock_acquired = await new_lock.acquire(
                token=holder, blocking_timeout=acquire_timeout
            )
            if lock_acquired:
                self._locks[lock_name] = new_lock
            return lock_acquired

        return False

    def release_lock(self, key: str, holder: str) -> None:
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and self.is_lock_holder(key, holder):
            lock.release()
            del self._locks[lock_name]
            return

        if not self.is_locked(key):  # is_locked calls _ensure_clients
            if lock_name in self._locks:
                del self._locks[lock_name]
            return

        raise ValueError(f"No lock held by {holder} for transaction with key {key}")

    async def arelease_lock(self, key: str, holder: str) -> None:  # Added async version
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and isinstance(
            lock, AsyncLock
        ):  # Still need to check if it *is* an AsyncLock to call await .owned()
            if await lock.owned() and lock.local.token == holder.encode():
                await lock.release()
                del self._locks[lock_name]
                return

        # Check if the lock key exists on the server at all.
        if not AsyncLock(self.async_client, lock_name).locked():
            # If the lock doesn't exist on the server, it's already effectively released.
            # Clean up from self._locks if it was there but holder didn't match.
            if lock_name in self._locks:
                del self._locks[lock_name]
            return

        raise ValueError(
            f"No lock held by {holder} for transaction with key {key} (async)"
        )

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)  # Create a temporary lock for waiting
        lock_freed = lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            lock.release()
        return lock_freed

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        assert self.async_client is not None, "Async client should be initialized"
        lock = AsyncLock(
            self.async_client, lock_name
        )  # Create a temporary lock for waiting
        lock_freed = await lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            await lock.release()
        return lock_freed

    def is_locked(self, key: str) -> bool:
        self._ensure_clients()
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)  # Create a temporary lock for checking
        return lock.locked()

    def is_lock_holder(self, key: str, holder: str) -> bool:
        self._ensure_clients()  # Ensures self.client is available if needed by _locks access logic
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        if (token := getattr(lock.local, "token", None)) is None:
            return False
        return token.decode() == holder
