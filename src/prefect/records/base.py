import os
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from prefect.results import BaseResult


class RecordStore:
    def read(self, key: str):
        raise NotImplementedError

    def write(self, key: str, value: dict):
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return False

    def acquire_lock(
        self,
        key: str,
        holder: Optional[str] = None,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire a lock for a transaction record with the given key. Will block other
        actors from updating this transaction record until the lock is
        released.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. If not provided,
                a default holder based on the current host, process, and thread will
                be used.
            acquire_timeout: Max number of seconds to wait for the record to become
                available if it is locked while attempting to acquire a lock. Pass 0
                to attempt to acquire a lock without waiting. Blocks indefinitely by
                default.
            hold_timeout: Max number of seconds to hold the lock for. Holds the lock
                indefinitely by default.

        Returns:
            bool: True if the lock was successfully acquired; False otherwise.
        """
        raise NotImplementedError

    def release_lock(self, key: str, holder: Optional[str] = None):
        """
        Releases the lock on the corresponding transaction record.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. Must match the
                holder provided when acquiring the lock.
        """
        raise NotImplementedError

    def is_locked(self, key: str) -> bool:
        """
        Simple check to see if the corresponding record is currently locked.

        Args:
            key: Unique identifier for the transaction record.

        Returns:
            True is the record is locked; False otherwise.
        """
        raise NotImplementedError

    def is_lock_holder(self, key: str, holder: Optional[str] = None) -> bool:
        """
        Check if the current holder is the lock holder for the transaction record.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. If not provided,
                a default holder based on the current host, process, and thread will
                be used.

        Returns:
            bool: True if the current holder is the lock holder; False otherwise.
        """
        raise NotImplementedError

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

    @staticmethod
    def generate_default_holder() -> str:
        """
        Generate a default holder string using hostname, PID, and thread ID.

        Returns:
            str: A unique identifier string.
        """
        hostname = socket.gethostname()
        pid = os.getpid()
        thread_name = threading.current_thread().name
        thread_id = threading.get_ident()
        return f"{hostname}:{pid}:{thread_id}:{thread_name}"

    @contextmanager
    def lock(
        self,
        key: str,
        holder: Optional[str] = None,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ):
        """
        Context manager to lock the transaction record during the execution
        of the nested code block.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. If not provided,
                a default holder based on the current host, process, and thread will
                be used.
            acquire_timeout: Max number of seconds to wait for the record to become
                available if it is locked while attempting to acquire a lock. Pass 0
                to attempt to acquire a lock without waiting. Blocks indefinitely by
                default.
            hold_timeout: Max number of seconds to hold the lock for. Holds the lock
                indefinitely by default.

        Example:
            Hold a lock while during an operation:
                ```python
                    with TransactionRecord(key="my-transaction-record-key").lock():
                        do_stuff()
                ```
        """
        self.acquire_lock(
            key=key,
            holder=holder,
            acquire_timeout=acquire_timeout,
            hold_timeout=hold_timeout,
        )

        try:
            yield
        finally:
            self.release_lock(key=key, holder=holder)


@dataclass
class TransactionRecord:
    """
    A dataclass representation of a transaction record.
    """

    key: str
    result: Optional[BaseResult] = None
