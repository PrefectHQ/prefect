import time
from datetime import timedelta
from logging import Logger
from pathlib import Path
from typing import Optional

import anyio
import pydantic_core
from typing_extensions import TypedDict

from prefect.logging.loggers import get_logger
from prefect.types._datetime import DateTime, now, parse_datetime

from .protocol import LockManager

logger: Logger = get_logger(__name__)


class _LockInfo(TypedDict):
    """
    A dictionary containing information about a lock.

    Attributes:
        holder: The holder of the lock.
        expiration: Datetime when the lock expires.
        path: Path to the lock file.
    """

    holder: str
    expiration: Optional[DateTime]
    path: Path


class FileSystemLockManager(LockManager):
    """
    A lock manager that implements locking using local files.

    Attributes:
        lock_files_directory: the directory where lock files are stored
    """

    def __init__(self, lock_files_directory: Path) -> None:
        self.lock_files_directory: Path = lock_files_directory.expanduser().resolve()
        self._locks: dict[str, _LockInfo] = {}

    def _ensure_lock_files_directory_exists(self) -> None:
        self.lock_files_directory.mkdir(parents=True, exist_ok=True)

    def _lock_path_for_key(self, key: str) -> Path:
        if (lock_info := self._locks.get(key)) is not None:
            return lock_info["path"]
        return self.lock_files_directory.joinpath(key).with_suffix(".lock")

    def _get_lock_info(self, key: str, use_cache: bool = True) -> Optional[_LockInfo]:
        if use_cache:
            if (lock_info := self._locks.get(key)) is not None:
                return lock_info

        lock_path = self._lock_path_for_key(key)

        try:
            with open(lock_path, "rb") as lock_file:
                lock_info = pydantic_core.from_json(lock_file.read())
                lock_info["path"] = lock_path
                expiration = lock_info.get("expiration")
                lock_info["expiration"] = (
                    parse_datetime(expiration) if expiration is not None else None
                )
            self._locks[key] = lock_info
            return lock_info
        except FileNotFoundError:
            return None

    async def _aget_lock_info(
        self, key: str, use_cache: bool = True
    ) -> Optional[_LockInfo]:
        if use_cache:
            if (lock_info := self._locks.get(key)) is not None:
                return lock_info

        lock_path = self._lock_path_for_key(key)

        try:
            lock_info_bytes = await anyio.Path(lock_path).read_bytes()
            lock_info = pydantic_core.from_json(lock_info_bytes)
            lock_info["path"] = lock_path
            expiration = lock_info.get("expiration")
            lock_info["expiration"] = (
                parse_datetime(expiration) if expiration is not None else None
            )
            self._locks[key] = lock_info
            return lock_info
        except FileNotFoundError:
            return None

    def acquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        self._ensure_lock_files_directory_exists()
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
            now("UTC") + timedelta(seconds=hold_timeout)
            if hold_timeout is not None
            else None
        )

        with open(Path(lock_path), "wb") as lock_file:
            lock_file.write(
                pydantic_core.to_json(
                    {
                        "holder": holder,
                        "expiration": str(expiration)
                        if expiration is not None
                        else None,
                    },
                )
            )

        self._locks[key] = {
            "holder": holder,
            "expiration": expiration,
            "path": lock_path,
        }

        return True

    async def aacquire_lock(
        self,
        key: str,
        holder: str,
        acquire_timeout: Optional[float] = None,
        hold_timeout: Optional[float] = None,
    ) -> bool:
        await anyio.Path(self.lock_files_directory).mkdir(parents=True, exist_ok=True)
        lock_path = self._lock_path_for_key(key)

        if self.is_locked(key) and not self.is_lock_holder(key, holder):
            lock_free = await self.await_for_lock(key, acquire_timeout)
            if not lock_free:
                return False

        try:
            await anyio.Path(lock_path).touch(exist_ok=False)
        except FileExistsError:
            if not self.is_lock_holder(key, holder):
                logger.debug(
                    f"Another actor acquired the lock for record with key {key}. Trying again."
                )
                return self.acquire_lock(key, holder, acquire_timeout, hold_timeout)
        expiration = (
            now("UTC") + timedelta(seconds=hold_timeout)
            if hold_timeout is not None
            else None
        )

        async with await anyio.Path(lock_path).open("wb") as lock_file:
            await lock_file.write(
                pydantic_core.to_json(
                    {
                        "holder": holder,
                        "expiration": str(expiration)
                        if expiration is not None
                        else None,
                    },
                )
            )

        self._locks[key] = {
            "holder": holder,
            "expiration": expiration,
            "path": lock_path,
        }

        return True

    def release_lock(self, key: str, holder: str) -> None:
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

        expired = expiration < now("UTC")
        if expired:
            Path(lock_info["path"]).unlink()
            self._locks.pop(key, None)
            return False
        else:
            return True

    def is_lock_holder(self, key: str, holder: str) -> bool:
        if not self.is_locked(key):
            return False

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

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        seconds_waited = 0
        while self.is_locked(key, use_cache=False):
            if timeout and seconds_waited >= timeout:
                return False
            seconds_waited += 0.1
            await anyio.sleep(0.1)
        return True
