import json
import time
from pathlib import Path
from typing import Optional

import pendulum

from prefect.logging.loggers import get_logger
from prefect.records.base import RecordStore, TransactionRecord
from prefect.results import BaseResult
from prefect.settings import PREFECT_RECORD_STORE_PATH
from prefect.transactions import IsolationLevel

logger = get_logger(__name__)


class FileSystemRecordStore(RecordStore):
    """
    A record store that stores data on the local filesystem.

    Locking is implemented using a lock file with the same name as the record file,
    but with a `.lock` extension.

    Attributes:
        records_directory: the directory where records are stored; defaults to
            `{PREFECT_HOME}/records`
    """

    def __init__(self, records_directory: Optional[Path] = None):
        self.records_directory = records_directory or PREFECT_RECORD_STORE_PATH.value()

    def _ensure_records_directory_exists(self):
        self.records_directory.mkdir(parents=True, exist_ok=True)

    def _lock_path_for_key(self, key: str) -> Path:
        return self.records_directory.joinpath(key).with_suffix(".lock")

    def read(
        self, key: str, holder: Optional[str] = None
    ) -> Optional[TransactionRecord]:
        if not self.exists(key):
            return None

        holder = holder or self.generate_default_holder()

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            self.wait_for_lock(key)
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

        with open(Path(lock_path), "w") as lock_file:
            lock_info = {"holder": holder}
            if hold_timeout:
                lock_info["expiration"] = str(
                    pendulum.now("utc") + pendulum.duration(seconds=hold_timeout)
                )
            json.dump(lock_info, lock_file)

        return True

    def release_lock(self, key: str, holder: Optional[str] = None) -> None:
        holder = holder or self.generate_default_holder()
        lock_path = self._lock_path_for_key(key)
        if not self.is_locked(key):
            ValueError(f"No lock for transaction with key {key}")
        if self.is_lock_holder(key, holder):
            Path(lock_path).unlink()
        else:
            raise ValueError(f"No lock held by {holder} for transaction with key {key}")

    def is_locked(self, key: str) -> bool:
        lock_path = self._lock_path_for_key(key)
        try:
            with open(Path(lock_path)) as lock_file:
                lock_info = json.load(lock_file)
        except FileNotFoundError:
            return False

        if (expiration := lock_info.get("expiration")) is None:
            return True

        expired = pendulum.parse(expiration) < pendulum.now("utc")
        if expired:
            Path(lock_path).unlink()
            return False
        else:
            return True

    def is_lock_holder(self, key: str, holder: Optional[str] = None) -> bool:
        if not self.is_locked(key):
            return False

        holder = holder or self.generate_default_holder()
        lock_path = self._lock_path_for_key(key)
        if not self.is_locked(key):
            return False
        try:
            with open(Path(lock_path), "r") as lock_file:
                lock_info = json.load(lock_file)
                return lock_info.get("holder") == holder
        except FileNotFoundError:
            return False

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        seconds_waited = 0
        while self.is_locked(key):
            if timeout and seconds_waited >= timeout:
                return False
            seconds_waited += 0.1
            time.sleep(0.1)
        return True
