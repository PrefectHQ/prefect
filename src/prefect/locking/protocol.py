from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LockManager(Protocol):
    def acquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire a lock for a transaction record with the given key. Will block other
        actors from updating this transaction record until the lock is
        released.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock.
            acquire_timeout: Max number of seconds to wait for the record to become
                available if it is locked while attempting to acquire a lock. Pass 0
                to attempt to acquire a lock without waiting. Blocks indefinitely by
                default.
            hold_timeout: Max number of seconds to hold the lock for. Holds the lock
                indefinitely by default.

        Returns:
            bool: True if the lock was successfully acquired; False otherwise.
        """
        ...

    async def aacquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire a lock for a transaction record with the given key. Will block other
        actors from updating this transaction record until the lock is
        released.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock.
            acquire_timeout: Max number of seconds to wait for the record to become
                available if it is locked while attempting to acquire a lock. Pass 0
                to attempt to acquire a lock without waiting. Blocks indefinitely by
                default.
            hold_timeout: Max number of seconds to hold the lock for. Holds the lock
                indefinitely by default.

        Returns:
            bool: True if the lock was successfully acquired; False otherwise.
        """
        ...

    def release_lock(self, key: str, holder: str) -> None:
        """
        Releases the lock on the corresponding transaction record.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. Must match the
                holder provided when acquiring the lock.
        """
        ...

    def is_locked(self, key: str) -> bool:
        """
        Simple check to see if the corresponding record is currently locked.

        Args:
            key: Unique identifier for the transaction record.

        Returns:
            True is the record is locked; False otherwise.
        """
        ...

    def is_lock_holder(self, key: str, holder: str) -> bool:
        """
        Check if the current holder is the lock holder for the transaction record.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock.

        Returns:
            bool: True if the current holder is the lock holder; False otherwise.
        """
        ...

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        """
        Wait for the corresponding transaction record to become free.

        Args:
            key: Unique identifier for the transaction record.
            timeout: Maximum time to wait. None means to wait indefinitely.

        Returns:
            bool: True if the lock becomes free within the timeout; False
                otherwise.
        """
        ...

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        """
        Wait for the corresponding transaction record to become free.

        Args:
            key: Unique identifier for the transaction record.
            timeout: Maximum time to wait. None means to wait indefinitely.

        Returns:
            bool: True if the lock becomes free within the timeout; False
                otherwise.
        """
        ...
