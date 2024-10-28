import asyncio
import threading
from typing import Dict, Optional, TypedDict

from .protocol import LockManager


class _LockInfo(TypedDict):
    """
    A dictionary containing information about a lock.

    Attributes:
        holder: The holder of the lock.
        lock: The lock object.
        expiration_timer: The timer for the lock expiration
    """

    holder: str
    lock: threading.Lock
    expiration_timer: Optional[threading.Timer]


class MemoryLockManager(LockManager):
    """
    A lock manager that stores lock information in memory.

    Note: because this lock manager stores data in memory, it is not suitable for
    use in a distributed environment or across different processes.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._locks_dict_lock = threading.Lock()
        self._locks: Dict[str, _LockInfo] = {}

    def _expire_lock(self, key: str):
        """
        Expire the lock for the given key.

        Used as a callback for the expiration timer of a lock.

        Args:
            key: The key of the lock to expire.
        """
        with self._locks_dict_lock:
            if key in self._locks:
                lock_info = self._locks[key]
                if lock_info["lock"].locked():
                    lock_info["lock"].release()
                if lock_info["expiration_timer"]:
                    lock_info["expiration_timer"].cancel()
                del self._locks[key]

    def acquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        with self._locks_dict_lock:
            if key not in self._locks:
                lock = threading.Lock()
                lock.acquire()
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(key,)
                    )
                    expiration_timer.start()
                self._locks[key] = _LockInfo(
                    holder=holder, lock=lock, expiration_timer=expiration_timer
                )
                return True
            elif self._locks[key]["holder"] == holder:
                return True
            else:
                existing_lock_info = self._locks[key]

        if acquire_timeout is not None:
            existing_lock_acquired = existing_lock_info["lock"].acquire(
                timeout=acquire_timeout
            )
        else:
            existing_lock_acquired = existing_lock_info["lock"].acquire()

        if existing_lock_acquired:
            with self._locks_dict_lock:
                if (
                    expiration_timer := existing_lock_info["expiration_timer"]
                ) is not None:
                    expiration_timer.cancel()
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(key,)
                    )
                    expiration_timer.start()
                self._locks[key] = _LockInfo(
                    holder=holder,
                    lock=existing_lock_info["lock"],
                    expiration_timer=expiration_timer,
                )
            return True
        return False

    async def aacquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        with self._locks_dict_lock:
            if key not in self._locks:
                lock = threading.Lock()
                await asyncio.to_thread(lock.acquire)
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(key,)
                    )
                    expiration_timer.start()
                self._locks[key] = _LockInfo(
                    holder=holder, lock=lock, expiration_timer=expiration_timer
                )
                return True
            elif self._locks[key]["holder"] == holder:
                return True
            else:
                existing_lock_info = self._locks[key]

        if acquire_timeout is not None:
            existing_lock_acquired = await asyncio.to_thread(
                existing_lock_info["lock"].acquire, timeout=acquire_timeout
            )
        else:
            existing_lock_acquired = await asyncio.to_thread(
                existing_lock_info["lock"].acquire
            )

        if existing_lock_acquired:
            with self._locks_dict_lock:
                if (
                    expiration_timer := existing_lock_info["expiration_timer"]
                ) is not None:
                    expiration_timer.cancel()
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(key,)
                    )
                    expiration_timer.start()
                self._locks[key] = _LockInfo(
                    holder=holder,
                    lock=existing_lock_info["lock"],
                    expiration_timer=expiration_timer,
                )
            return True
        return False

    def release_lock(self, key: str, holder: str) -> None:
        with self._locks_dict_lock:
            if key in self._locks and self._locks[key]["holder"] == holder:
                if (
                    expiration_timer := self._locks[key]["expiration_timer"]
                ) is not None:
                    expiration_timer.cancel()
                self._locks[key]["lock"].release()
                del self._locks[key]
            else:
                raise ValueError(
                    f"No lock held by {holder} for transaction with key {key}"
                )

    def is_locked(self, key: str) -> bool:
        return key in self._locks and self._locks[key]["lock"].locked()

    def is_lock_holder(self, key: str, holder: str) -> bool:
        lock_info = self._locks.get(key)
        return (
            lock_info is not None
            and lock_info["lock"].locked()
            and lock_info["holder"] == holder
        )

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        if lock := self._locks.get(key, {}).get("lock"):
            if timeout is not None:
                lock_acquired = lock.acquire(timeout=timeout)
            else:
                lock_acquired = lock.acquire()
            if lock_acquired:
                lock.release()
            return lock_acquired
        return True

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        if lock := self._locks.get(key, {}).get("lock"):
            if timeout is not None:
                lock_acquired = await asyncio.to_thread(lock.acquire, timeout=timeout)
            else:
                lock_acquired = await asyncio.to_thread(lock.acquire)
            if lock_acquired:
                lock.release()
            return lock_acquired
        return True
