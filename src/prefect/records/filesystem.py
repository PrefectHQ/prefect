import json
import time
from pathlib import Path
from typing import Dict, Optional

import pendulum
from typing_extensions import TypedDict

from prefect._internal.compatibility import deprecated
from prefect.logging.loggers import get_logger
from prefect.records.base import RecordStore, TransactionRecord
from prefect.results import BaseResult
from prefect.transactions import IsolationLevel

logger = get_logger(__name__)


class _LockInfo(TypedDict):
    """
    A dictionary containing information about a lock.

    Attributes:
        holder: The holder of the lock.
        expiration: Datetime when the lock expires.
        path: Path to the lock file.
    """

    holder: str
    expiration: Optional[pendulum.DateTime]
    path: Path


@deprecated.deprecated_class(
    start_date="Sep 2024",
    end_date="Nov 2024",
    help="Use `ResultStore` with a `LocalFileSystem` for `metadata_storage` and a `FileSystemLockManager` instead.",
)
class FileSystemRecordStore(RecordStore):
    """
    A record store that stores data on the local filesystem.

    Locking is implemented using a lock file with the same name as the record file,
    but with a `.lock` extension.

    Attributes:
        records_directory: the directory where records are stored; defaults to
            `{PREFECT_HOME}/records`
    """

    def __init__(self, records_directory: Path):
        self.records_directory = records_directory
        self._locks: Dict[str, _LockInfo] = {}

    def _ensure_records_directory_exists(self):
        self.records_directory.mkdir(parents=True, exist_ok=True)

    def _lock_path_for_key(self, key: str) -> Path:
        if (lock_info := self._locks.get(key)) is not None:
            return lock_info["path"]
        return self.records_directory.joinpath(key).with_suffix(".lock")

    def _get_lock_info(self, key: str, use_cache=True) -> Optional[_LockInfo]:
        if use_cache:
            if (lock_info := self._locks.get(key)) is not None:
                return lock_info

        lock_path = self._lock_path_for_key(key)

        try:
            with open(lock_path, "r") as lock_file:
                lock_info = json.load(lock_file)
                lock_info["path"] = lock_path
                expiration = lock_info.get("expiration")
                lock_info["expiration"] = (
                    pendulum.parse(expiration) if expiration is not None else None
                )
            self._locks[key] = lock_info
            return lock_info
        except FileNotFoundError:
            return None

    def read(
        self, key: str, holder: Optional[str] = None, timeout: Optional[float] = None
    ) -> Optional[TransactionRecord]:
        if not self.exists(key):
            return None

        holder = holder or self.generate_default_holder()

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            unlocked = self.wait_for_lock(key, timeout=timeout)
            if not unlocked:
                return None
        record_data = self.records_directory.joinpath(key).read_text()
        return TransactionRecord(
            key=key, result=BaseResult.model_validate_json(record_data)
        )

    def write(self, key: str, result: BaseResult, holder: Optional[str] = None) -> None:
        self._ensure_records_directory_exists()

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            raise ValueError(
                f"Cannot write to transaction with key {key} because it is locked by another holder."
            )

        record_path = self.records_directory.joinpath(key)
        record_path.touch(exist_ok=True)
        record_data = result.model_dump_json()
        record_path.write_text(record_data)

    def exists(self, key: str) -> bool:
        return self.records_directory.joinpath(key).exists()

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

        self._ensure_records_directory_exists()
        lock_path = self._lock_path_for_key(key)

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            lock_free = self.wait_for_lock(key, acquire_timeout)
            if not lock_free:
                return False

        try:
            Path(lock_path).touch(exist_ok=False)
        except FileExistsError:
            if not self.is_lock_holder(key, holder):
                logger.debug(
                    f"Another actor acquired the lock for record with key {key}. Trying again."
                )
                return self.acquire_lock(key, holder, acquire_timeout, hold_timeout)
        expiration = (
            pendulum.now("utc") + pendulum.duration(seconds=hold_timeout)
            if hold_timeout is not None
            else None
        )

        with open(Path(lock_path), "w") as lock_file:
            json.dump(
                {
                    "holder": holder,
                    "expiration": str(expiration) if expiration is not None else None,
                },
                lock_file,
            )

        self._locks[key] = {
            "holder": holder,
            "expiration": expiration,
            "path": lock_path,
        }

        return True

    def release_lock(self, key: str, holder: Optional[str] = None) -> None:
        holder = holder or self.generate_default_holder()
        lock_path = self._lock_path_for_key(key)
        if not self.is_locked(key):
            ValueError(f"No lock for transaction with key {key}")
        if self.is_lock_holder(key, holder):
            Path(lock_path).unlink(missing_ok=True)
            self._locks.pop(key, None)
        else:
            raise ValueError(f"No lock held by {holder} for transaction with key {key}")

    def is_locked(self, key: str, use_cache: bool = False) -> bool:
        if (lock_info := self._get_lock_info(key, use_cache=use_cache)) is None:
            return False

        if (expiration := lock_info.get("expiration")) is None:
            return True

        expired = expiration < pendulum.now("utc")
        if expired:
            Path(lock_info["path"]).unlink()
            self._locks.pop(key, None)
            return False
        else:
            return True

    def is_lock_holder(self, key: str, holder: Optional[str] = None) -> bool:
        if not self.is_locked(key):
            return False

        holder = holder or self.generate_default_holder()
        if not self.is_locked(key):
            return False
        if (lock_info := self._get_lock_info(key)) is None:
            return False
        return lock_info["holder"] == holder

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        seconds_waited = 0
        while self.is_locked(key, use_cache=False):
            if timeout and seconds_waited >= timeout:
                return False
            seconds_waited += 0.1
            time.sleep(0.1)
        return True
