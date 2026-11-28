import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import anyio
import pytest

from prefect.locking import filesystem
from prefect.locking.filesystem import FileSystemLockManager
from prefect.types._datetime import now


class _Clock:
    """A clock that tracks real time with a controllable offset."""

    def __init__(self) -> None:
        self.offset = timedelta()

    def now(self, tz: str = "UTC") -> datetime:
        return now(tz) + self.offset

    def advance(self, seconds: float) -> None:
        self.offset += timedelta(seconds=seconds)


class TestFileSystemLockManagerAsyncAndTimeout:
    @pytest.fixture
    def manager(self, tmp_path: Path) -> FileSystemLockManager:
        return FileSystemLockManager(lock_files_directory=tmp_path)

    @pytest.fixture
    def clock(self, monkeypatch: pytest.MonkeyPatch) -> _Clock:
        clock = _Clock()
        monkeypatch.setattr(filesystem, "now", clock.now)
        return clock

    async def test_aacquire_lock_contention_does_not_block_event_loop(
        self, manager: FileSystemLockManager, monkeypatch: pytest.MonkeyPatch
    ):
        """When another holder wins the file-creation race, `aacquire_lock` must
        retry asynchronously instead of calling synchronous `acquire_lock`,
        which would block the event loop and deadlock same-loop holders."""
        key = str(uuid4())
        raced = False
        original_is_locked = manager.is_locked

        def is_locked_with_race(check_key: str, use_cache: bool = False) -> bool:
            nonlocal raced
            if not raced and check_key == key:
                raced = True
                # Simulate holder1 acquiring the lock right after holder2 sees
                # the key as unlocked, forcing holder2 into the FileExistsError
                # retry branch.
                assert manager.acquire_lock(key, holder="holder1")
                return False
            return original_is_locked(check_key, use_cache=use_cache)

        monkeypatch.setattr(manager, "is_locked", is_locked_with_race)

        async def release_holder1() -> None:
            await anyio.sleep(0.05)
            manager.release_lock(key, holder="holder1")

        releaser = asyncio.create_task(release_holder1())
        try:
            acquired = await manager.aacquire_lock(
                key, holder="holder2", acquire_timeout=1.0
            )
        finally:
            await releaser

        assert acquired is True
        assert manager.is_lock_holder(key, holder="holder2")
        manager.release_lock(key, holder="holder2")

    async def test_aacquire_lock_concurrent_coroutines_mutual_exclusion(
        self, manager: FileSystemLockManager
    ):
        """Concurrent coroutines racing on the same key must observe mutual
        exclusion without deadlocking or reading partially written lock files."""
        key = str(uuid4())
        active = 0
        max_active = 0
        completed: list[str] = []

        async def worker(holder: str) -> None:
            nonlocal active, max_active
            assert await manager.aacquire_lock(key, holder=holder, acquire_timeout=5.0)
            active += 1
            max_active = max(max_active, active)
            await anyio.sleep(0.02)
            active -= 1
            completed.append(holder)
            manager.release_lock(key, holder=holder)

        await asyncio.gather(*(worker(f"holder-{i}") for i in range(4)))
        assert max_active == 1
        assert len(completed) == 4
        assert not manager.is_locked(key)

    def test_wait_for_lock_zero_timeout_returns_false_immediately(
        self, manager: FileSystemLockManager
    ):
        key = str(uuid4())
        assert manager.acquire_lock(key, holder="holder1")
        timer = threading.Timer(0.25, manager.release_lock, args=(key, "holder1"))
        timer.start()
        try:
            assert manager.wait_for_lock(key, timeout=0) is False
            assert manager.is_lock_holder(key, holder="holder1")
        finally:
            timer.cancel()
            manager.release_lock(key, holder="holder1")

    async def test_await_for_lock_zero_timeout_returns_false_immediately(
        self, manager: FileSystemLockManager
    ):
        key = str(uuid4())
        assert await manager.aacquire_lock(key, holder="holder1")

        async def release_later() -> None:
            await anyio.sleep(0.25)
            manager.release_lock(key, holder="holder1")

        releaser = asyncio.create_task(release_later())
        try:
            assert await manager.await_for_lock(key, timeout=0) is False
            assert manager.is_lock_holder(key, holder="holder1")
        finally:
            releaser.cancel()
            try:
                await releaser
            except asyncio.CancelledError:
                pass
            manager.release_lock(key, holder="holder1")

    def test_acquire_lock_zero_timeout_returns_false_immediately(
        self, manager: FileSystemLockManager
    ):
        key = str(uuid4())
        assert manager.acquire_lock(key, holder="holder1")
        timer = threading.Timer(0.25, manager.release_lock, args=(key, "holder1"))
        timer.start()
        try:
            assert (
                manager.acquire_lock(key, holder="holder2", acquire_timeout=0) is False
            )
            assert manager.is_lock_holder(key, holder="holder1")
        finally:
            timer.cancel()
            if manager.is_lock_holder(key, holder="holder1"):
                manager.release_lock(key, holder="holder1")
            elif manager.is_lock_holder(key, holder="holder2"):
                manager.release_lock(key, holder="holder2")

    async def test_aacquire_lock_zero_timeout_returns_false_immediately(
        self, manager: FileSystemLockManager
    ):
        key = str(uuid4())
        assert await manager.aacquire_lock(key, holder="holder1")

        async def release_later() -> None:
            await anyio.sleep(0.25)
            manager.release_lock(key, holder="holder1")

        releaser = asyncio.create_task(release_later())
        try:
            assert (
                await manager.aacquire_lock(key, holder="holder2", acquire_timeout=0)
                is False
            )
            assert manager.is_lock_holder(key, holder="holder1")
        finally:
            releaser.cancel()
            try:
                await releaser
            except asyncio.CancelledError:
                pass
            if manager.is_lock_holder(key, holder="holder1"):
                manager.release_lock(key, holder="holder1")
            elif manager.is_lock_holder(key, holder="holder2"):
                manager.release_lock(key, holder="holder2")

    def test_acquire_lock_zero_timeout_returns_false_on_creation_race(
        self, manager: FileSystemLockManager, monkeypatch: pytest.MonkeyPatch
    ):
        key = str(uuid4())
        raced = False
        original_is_locked = manager.is_locked

        def is_locked_with_race(check_key: str, use_cache: bool = False) -> bool:
            nonlocal raced
            if not raced and check_key == key:
                raced = True
                assert manager.acquire_lock(key, holder="holder1")
                return False
            return original_is_locked(check_key, use_cache=use_cache)

        monkeypatch.setattr(manager, "is_locked", is_locked_with_race)
        timer = threading.Timer(0.25, manager.release_lock, args=(key, "holder1"))
        timer.start()
        try:
            assert (
                manager.acquire_lock(key, holder="holder2", acquire_timeout=0) is False
            )
            assert manager.is_lock_holder(key, holder="holder1")
        finally:
            timer.cancel()
            if manager.is_lock_holder(key, holder="holder1"):
                manager.release_lock(key, holder="holder1")
            elif manager.is_lock_holder(key, holder="holder2"):
                manager.release_lock(key, holder="holder2")

    def test_is_locked_tolerates_concurrent_unlink_of_expired_lock(
        self,
        manager: FileSystemLockManager,
        clock: _Clock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        key = str(uuid4())
        assert manager.acquire_lock(key, holder="holder1", hold_timeout=10)
        clock.advance(11)

        original_get_lock_info = manager._get_lock_info

        def get_and_unlink(
            check_key: str, use_cache: bool = True
        ) -> filesystem._LockInfo | None:
            info = original_get_lock_info(check_key, use_cache=use_cache)
            if info is not None:
                Path(info["path"]).unlink(missing_ok=True)
            return info

        monkeypatch.setattr(manager, "_get_lock_info", get_and_unlink)
        assert manager.is_locked(key) is False
