import datetime
import os
import sys
import tempfile
import time
from datetime import timedelta
from logging import Logger
from pathlib import Path
from typing import Optional

import anyio
import anyio.to_thread
import pydantic_core
from typing_extensions import TypedDict

from prefect.logging.loggers import get_logger
from prefect.types._datetime import now, parse_datetime

from .protocol import LockManager

logger: Logger = get_logger(__name__)


def _serialize_lock_info(holder: str, expiration: Optional[datetime.datetime]) -> bytes:
    return pydantic_core.to_json(
        {
            "holder": holder,
            "expiration": str(expiration) if expiration is not None else None,
        }
    )


def _create_lock_file(lock_path: Path, data: bytes) -> None:
    """Atomically create a lock file populated with `data`.

    Writes `data` to a sibling temporary file and hard-links it into place so
    concurrent readers never observe an empty or partially written lock file.
    Falls back to `open(..., "xb")` on filesystems without hard-link support.
    Raises `FileExistsError` if `lock_path` already exists.
    """
    fd, tmp_path = tempfile.mkstemp(dir=lock_path.parent, prefix=".lock_")
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            fd = -1
            tmp_file.write(data)
        try:
            os.link(tmp_path, lock_path)
        except FileExistsError:
            raise
        except OSError:
            with open(lock_path, "xb") as lock_file:
                lock_file.write(data)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


def _unlink_lock_file(lock_path: Path) -> None:
    """Remove `lock_path`, ignoring missing files and retrying transient Windows sharing errors."""
    for attempt in range(5):
        try:
            lock_path.unlink(missing_ok=True)
            return
        except PermissionError:
            if sys.platform != "win32" or attempt == 4:
                raise
            time.sleep(0.01)


class _LockInfo(TypedDict):
    """
    A dictionary containing information about a lock.

    Attributes:
        holder: The holder of the lock.
        expiration: Datetime when the lock expires.
        path: Path to the lock file.
    """

    holder: str
    expiration: Optional[datetime.datetime]
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
        deadline = (
            time.monotonic() + acquire_timeout if acquire_timeout is not None else None
        )

        while True:
            if self.is_locked(key) and not self.is_lock_holder(key, holder):
                remaining = (
                    max(0.0, deadline - time.monotonic())
                    if deadline is not None
                    else None
                )
                lock_free = self.wait_for_lock(key, remaining)
                if not lock_free:
                    return False

            expiration = (
                now("UTC") + timedelta(seconds=hold_timeout)
                if hold_timeout is not None
                else None
            )
            lock_info_bytes = _serialize_lock_info(holder, expiration)

            try:
                _create_lock_file(lock_path, lock_info_bytes)
            except FileExistsError:
                if not self.is_lock_holder(key, holder):
                    if deadline is not None and time.monotonic() >= deadline:
                        return False
                    logger.debug(
                        f"Another actor acquired the lock for record with key {key}. Trying again."
                    )
                    continue
                with open(Path(lock_path), "wb") as lock_file:
                    lock_file.write(lock_info_bytes)
            break

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
        deadline = (
            time.monotonic() + acquire_timeout if acquire_timeout is not None else None
        )

        while True:
            if self.is_locked(key) and not self.is_lock_holder(key, holder):
                remaining = (
                    max(0.0, deadline - time.monotonic())
                    if deadline is not None
                    else None
                )
                lock_free = await self.await_for_lock(key, remaining)
                if not lock_free:
                    return False

            expiration = (
                now("UTC") + timedelta(seconds=hold_timeout)
                if hold_timeout is not None
                else None
            )
            lock_info_bytes = _serialize_lock_info(holder, expiration)

            try:
                await anyio.to_thread.run_sync(
                    _create_lock_file, lock_path, lock_info_bytes
                )
            except FileExistsError:
                if not self.is_lock_holder(key, holder):
                    if deadline is not None and time.monotonic() >= deadline:
                        return False
                    logger.debug(
                        f"Another actor acquired the lock for record with key {key}. Trying again."
                    )
                    continue
                async with await anyio.Path(lock_path).open("wb") as lock_file:
                    await lock_file.write(lock_info_bytes)
            break

        self._locks[key] = {
            "holder": holder,
            "expiration": expiration,
            "path": lock_path,
        }

        return True

    def release_lock(self, key: str, holder: str) -> None:
        lock_path = self._lock_path_for_key(key)
        if self.is_lock_holder(key, holder):
            _unlink_lock_file(Path(lock_path))
            self._locks.pop(key, None)
            return
        if not self.is_locked(key):
            # The lock was already released or expired (e.g. its hold timeout
            # elapsed or it was released during a task retry) — including
            # between the checks above — so releasing it is a no-op, matching
            # RedisLockManager.
            self._locks.pop(key, None)
            return
        raise ValueError(f"No lock held by {holder} for transaction with key {key}")

    def is_locked(self, key: str, use_cache: bool = False) -> bool:
        if (lock_info := self._get_lock_info(key, use_cache=use_cache)) is None:
            return False

        if (expiration := lock_info.get("expiration")) is None:
            return True

        expired = expiration < now("UTC")
        if expired:
            _unlink_lock_file(Path(lock_info["path"]))
            self._locks.pop(key, None)
            return False
        else:
            return True

    def is_lock_holder(self, key: str, holder: str) -> bool:
        if not self.is_locked(key):
            return False
        if (lock_info := self._get_lock_info(key)) is None:
            return False
        return lock_info["holder"] == holder

    def wait_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while self.is_locked(key, use_cache=False):
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                time.sleep(min(0.1, remaining))
            else:
                time.sleep(0.1)
        return True

    async def await_for_lock(self, key: str, timeout: Optional[float] = None) -> bool:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while self.is_locked(key, use_cache=False):
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                await anyio.sleep(min(0.1, remaining))
            else:
                await anyio.sleep(0.1)
        return True
