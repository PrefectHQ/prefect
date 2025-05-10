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

    # internal
    def _ensure_clients(self) -> None:
        if self.client is None:
            self.client = Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ssl=self.ssl,  # Added ssl here
            )
        if self.async_client is None:  # Check for async_client separately
            self.async_client = AsyncRedis(
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ssl=self.ssl,  # Added ssl here
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
        assert self.client is not None, (
            "Client should be initialized by _ensure_clients"
        )
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        # Ensure lock is of correct type if it exists
        if lock is not None and not isinstance(lock, Lock):
            # If a lock exists but is an AsyncLock, it's a mixed usage scenario that needs re-evaluation for this sync method
            # For now, assume we should create a new sync lock or it's an error.
            # Simplest: re-create if type mismatch, or rely on is_lock_holder to also use sync client
            lock = None

        if lock is not None and self.is_lock_holder(
            key, holder
        ):  # is_lock_holder will also call _ensure_clients
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
        self._ensure_clients()
        assert self.async_client is not None, (
            "Async client should be initialized by _ensure_clients"
        )
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and isinstance(lock, AsyncLock):
            # Use await lock.owned() for a proper async check
            if await lock.owned(
                token=holder.encode()
            ):  # Check if this specific lock instance is owned by the holder
                return True
            else:  # Lock exists in self._locks but token doesn't match or it's expired on server
                # Treat as if lock is not held by current holder, so proceed to acquire
                lock = None

        # If lock is None (not in self._locks or holder didn't match/was stale), try to acquire a new one
        if (
            lock is None
        ):  # Renamed from 'else:' to be clearer after the modification above
            new_lock = AsyncLock(
                self.async_client, lock_name, timeout=hold_timeout, thread_local=False
            )
            lock_acquired = await new_lock.acquire(
                token=holder, blocking_timeout=acquire_timeout
            )
            if lock_acquired:
                self._locks[lock_name] = new_lock
            return lock_acquired

        return False  # Should have returned True earlier if lock was held and owned

    def release_lock(self, key: str, holder: str) -> None:
        self._ensure_clients()  # Needed for is_locked check and potentially Lock re-creation if not in self._locks
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and self.is_lock_holder(key, holder):
            assert isinstance(lock, Lock), "Lock in _locks should match sync context"
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
        assert self.async_client is not None, "Async client should be initialized"
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)

        if lock is not None and isinstance(lock, AsyncLock):
            # Use await lock.owned() for a proper async check before attempting release
            if await lock.owned(token=holder.encode()):
                await lock.release()
                del self._locks[lock_name]
                return
            # If lock in self._locks but not owned by this holder (e.g. token mismatch, or expired on server)
            # Fall through to check if lock exists on server at all before raising ValueError

        # Fallback: If lock wasn't in self._locks, or if it was but not owned by the current holder.
        # Check if the lock key exists on the server at all.
        # AsyncLock(...).locked() is a synchronous check on a new instance.
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
        assert self.client is not None, "Client should be initialized"
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)  # Create a temporary lock for waiting
        lock_freed = lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            lock.release()
        return lock_freed

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        self._ensure_clients()
        assert self.async_client is not None, "Async client should be initialized"
        lock_name = self._lock_name_for_key(key)
        lock = AsyncLock(
            self.async_client, lock_name
        )  # Create a temporary lock for waiting
        lock_freed = await lock.acquire(blocking_timeout=timeout)
        if lock_freed:
            await lock.release()
        return lock_freed

    def is_locked(self, key: str) -> bool:
        self._ensure_clients()
        assert self.client is not None, "Client should be initialized"
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)  # Create a temporary lock for checking
        return lock.locked()

    def is_lock_holder(self, key: str, holder: str) -> bool:
        self._ensure_clients()  # Ensures self.client is available if needed by _locks access logic
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        # Ensure the lock in _locks is the correct type (sync)
        if not isinstance(lock, Lock):
            # This case implies mixed sync/async usage on the same key with the same manager instance,
            # which might be problematic. For now, if it's an AsyncLock, it can't be the holder in a sync context.
            return False
        if (token := getattr(lock.local, "token", None)) is None:
            return False
        return token.decode() == holder
