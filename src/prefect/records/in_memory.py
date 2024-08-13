import threading
from typing import Dict, Optional, TypedDict

from .base import TransactionRecord

_locks_dict_lock = threading.Lock()


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


_locks: Dict[str, _LockInfo] = {}


class InMemoryTransactionRecord(TransactionRecord):
    """
    A transaction record that stores locks in memory.
    """

    @staticmethod
    def _expire_lock(key: str):
        """
        Expire the lock for the given key.

        Used as a callback for the expiration timer of a lock.

        Args:
            key: The key of the lock to expire.
        """
        with _locks_dict_lock:
            if key in _locks:
                lock_info = _locks[key]
                if lock_info["lock"].locked():
                    lock_info["lock"].release()
                if lock_info["expiration_timer"]:
                    lock_info["expiration_timer"].cancel()
                del _locks[key]

    def acquire_lock(
        self,
        holder: str | None = None,
        acquire_timeout: float | None = None,
        hold_timeout: float | None = None,
    ) -> bool:
        holder = holder or self.generate_default_holder()
        with _locks_dict_lock:
            if self.key not in _locks:
                lock = threading.Lock()
                lock.acquire()
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(self.key,)
                    )
                    expiration_timer.start()
                _locks[self.key] = _LockInfo(
                    holder=holder, lock=lock, expiration_timer=expiration_timer
                )
                return True
            elif _locks[self.key]["holder"] == holder:
                return True
            else:
                existing_lock_info = _locks[self.key]

        if acquire_timeout is not None:
            existing_lock_acquired = existing_lock_info["lock"].acquire(
                timeout=acquire_timeout
            )
        else:
            existing_lock_acquired = existing_lock_info["lock"].acquire()

        if existing_lock_acquired:
            with _locks_dict_lock:
                if (
                    expiration_timer := existing_lock_info["expiration_timer"]
                ) is not None:
                    expiration_timer.cancel()
                expiration_timer = None
                if hold_timeout is not None:
                    expiration_timer = threading.Timer(
                        hold_timeout, self._expire_lock, args=(self.key,)
                    )
                    expiration_timer.start()
                _locks[self.key] = _LockInfo(
                    holder=holder,
                    lock=existing_lock_info["lock"],
                    expiration_timer=expiration_timer,
                )
            return True
        return False

    def release_lock(self, holder: str | None = None) -> None:
        holder = holder or self.generate_default_holder()
        with _locks_dict_lock:
            if self.key in _locks and _locks[self.key]["holder"] == holder:
                if (
                    expiration_timer := _locks[self.key]["expiration_timer"]
                ) is not None:
                    expiration_timer.cancel()
                _locks[self.key]["lock"].release()
                del _locks[self.key]
            else:
                raise ValueError(
                    f"No lock held by {holder} for transaction with key {self.key}"
                )

    @property
    def is_locked(self) -> bool:
        return self.key in _locks and _locks[self.key]["lock"].locked()

    def wait_for_lock(self, timeout: float | None = None) -> bool:
        if lock := _locks.get(self.key, {}).get("lock"):
            if timeout is not None:
                lock_acquired = lock.acquire(timeout=timeout)
            else:
                lock_acquired = lock.acquire()
            if lock_acquired:
                lock.release()
            return lock_acquired
        return True
