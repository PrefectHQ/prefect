import abc
import os
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from prefect._internal.compatibility import deprecated

if TYPE_CHECKING:
    from prefect.results import BaseResult
    from prefect.transactions import IsolationLevel


@deprecated.deprecated_class(
    start_date="Sep 2024",
    end_date="Nov 2024",
    help="Use `ResultRecord` instead to represent a result and its associated metadata.",
)
@dataclass
class TransactionRecord:
    """
    A dataclass representation of a transaction record.
    """

    key: str
    result: "BaseResult"


@deprecated.deprecated_class(
    start_date="Sep 2024",
    end_date="Nov 2024",
    help="Use `ResultStore` and provide a `WritableFileSystem` for `metadata_storage` instead.",
)
class RecordStore(abc.ABC):
    @abc.abstractmethod
    def read(
        self, key: str, holder: Optional[str] = None
    ) -> Optional[TransactionRecord]:
        """
        Read the transaction record with the given key.

        Args:
            key: Unique identifier for the transaction record.
            holder: Unique identifier for the holder of the lock. If a lock exists on
                the record being written, the read will be blocked until the lock is
                released if the provided holder does not match the holder of the lock.
                If not provided, a default holder based on the current host, process,
                and thread will be used.

        Returns:
            TransactionRecord: The transaction record with the given key.
        """
        ...

    @abc.abstractmethod
    def write(self, key: str, result: "BaseResult", holder: Optional[str] = None):
        """
        Write the transaction record with the given key.

        Args:
            key: Unique identifier for the transaction record.
            record: The transaction record to write.
            holder: Unique identifier for the holder of the lock. If a lock exists on
                the record being written, the write will be rejected if the provided
                holder does not match the holder of the lock. If not provided,
                a default holder based on the current host, process, and thread will
                be used.
        """
        ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if the transaction record with the given key exists.

        Args:
            key: Unique identifier for the transaction record.

        Returns:
            bool: True if the record exists; False otherwise.
        """
        ...

    @abc.abstractmethod
    def supports_isolation_level(self, isolation_level: "IsolationLevel") -> bool:
        """
        Check if the record store supports the given isolation level.

        Args:
            isolation_level: The isolation level to check.

        Returns:
            bool: True if the record store supports the isolation level; False otherwise.
        """
        ...

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
