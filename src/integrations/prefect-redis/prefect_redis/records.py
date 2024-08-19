import math
from typing import Optional

import pendulum
from redis import Redis
from redis.lock import Lock

from prefect.records import RecordStore
from prefect.records.base import TransactionRecord
from prefect.results import BaseResult
from prefect.settings import (
    PREFECT_RECORD_STORE_REDIS_DB,
    PREFECT_RECORD_STORE_REDIS_HOST,
    PREFECT_RECORD_STORE_REDIS_PASSWORD,
    PREFECT_RECORD_STORE_REDIS_PORT,
    PREFECT_RECORD_STORE_REDIS_SSL,
    PREFECT_RECORD_STORE_REDIS_USERNAME,
)
from prefect.transactions import IsolationLevel


class RedisRecordStore(RecordStore):
    """
    A record store that uses Redis as a backend.

    Attributes:
        client: The Redis client used to communicate with the Redis server
        host: The host of the Redis server
        port: The port the Redis server is running on
        db: The database to write to and read from
        username: The username to use when connecting to the Redis server
        password: The password to use when connecting to the Redis server
        ssl: Whether to use SSL when connecting to the Redis server
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
    ) -> None:
        """
        Args:
            host: The host of the Redis server; defaults to the value of the
                PREFECT_RECORD_STORE_REDIS_HOST setting if not provided
            port: The port the Redis server is running on; defaults to the value of the
                PREFECT_RECORD_STORE_REDIS_PORT setting if not provided
            db: The database to write to and read from; defaults to the value of the
                PREFECT_RECORD_STORE_REDIS_DB setting if not provided
            username: The username to use when connecting to the Redis server; defaults
                to the value of the PREFECT_RECORD_STORE_REDIS_USERNAME setting if not
                provided
            password: The password to use when connecting to the Redis server; defaults
                to the value of the PREFECT_RECORD_STORE_REDIS_PASSWORD setting if not
                provided
            ssl: Whether to use SSL when connecting to the Redis server; defaults to the
                value of the PREFECT_RECORD_STORE_REDIS_SSL setting if not provided
        """
        self.host = host or PREFECT_RECORD_STORE_REDIS_HOST.value()
        self.port = port or PREFECT_RECORD_STORE_REDIS_PORT.value()
        self.db = db or PREFECT_RECORD_STORE_REDIS_DB.value()
        self.username = username or PREFECT_RECORD_STORE_REDIS_USERNAME.value()
        self.password = password or PREFECT_RECORD_STORE_REDIS_PASSWORD.value()
        self.ssl = ssl or PREFECT_RECORD_STORE_REDIS_SSL.value()
        self.client = Redis(
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

    def read(
        self, key: str, holder: Optional[str] = None
    ) -> Optional[TransactionRecord]:
        holder = holder or self.generate_default_holder()

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            self.wait_for_lock(key)

        serialized_result = self.client.get(name=key)
        if serialized_result is None:
            return None
        assert isinstance(serialized_result, bytes)
        return TransactionRecord(
            key=key, result=BaseResult.model_validate_json(serialized_result)
        )

    def write(self, key: str, result: BaseResult, holder: Optional[str] = None) -> None:
        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            raise ValueError(
                f"Cannot write to transaction with key {key} because it is locked by another holder."
            )
        ex = None
        if (
            expiration := getattr(result, "expiration", None)
        ) is not None and isinstance(expiration, pendulum.DateTime):
            ex = math.ceil((expiration - pendulum.now()).total_seconds())
        serialized_result = result.model_dump_json()
        self.client.set(name=key, value=serialized_result, ex=ex)

    def exists(self, key: str) -> bool:
        return bool(self.client.exists(key))

    def supports_isolation_level(self, isolation_level: IsolationLevel) -> bool:
        return isolation_level in {
            IsolationLevel.READ_COMMITTED,
            IsolationLevel.SERIALIZABLE,
        }

    def acquire_lock(
        self,
        key: str,
        holder: Optional[str] = None,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        holder = holder or self.generate_default_holder()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is not None and self.is_lock_holder(key, holder):
            return True
        else:
            lock = Lock(self.client, lock_name, timeout=hold_timeout)
        lock_acquired = lock.acquire(token=holder, blocking_timeout=acquire_timeout)
        if lock_acquired:
            self._locks[lock_name] = lock
        return lock_acquired

    def release_lock(self, key: str, holder: Optional[str] = None) -> None:
        holder = holder or self.generate_default_holder()
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

    def is_locked(self, key: str) -> bool:
        lock_name = self._lock_name_for_key(key)
        lock = Lock(self.client, lock_name)
        return lock.locked()

    def is_lock_holder(self, key: str, holder: Optional[str] = None) -> bool:
        holder = holder or self.generate_default_holder()
        lock_name = self._lock_name_for_key(key)
        lock = self._locks.get(lock_name)
        if lock is None:
            return False
        if (token := getattr(lock.local, "token", None)) is None:
            return False
        return token.decode() == holder
