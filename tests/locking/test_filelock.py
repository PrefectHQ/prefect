import asyncio
import os
import threading
from pathlib import Path

import pytest

from prefect.locking._filelock import (
    FileLock,
    _is_pid_alive,
    _remove_stale_lock,
    _write_lock,
)


class TestIsPidAlive:
    def test_current_process_is_alive(self):
        assert _is_pid_alive(os.getpid()) is True

    def test_nonexistent_pid_is_not_alive(self):
        # PID 0 is the kernel on Unix — we can't signal it, but a very
        # large PID is almost certainly unused.
        assert _is_pid_alive(4_000_000) is False


class TestRemoveStaleLock:
    def test_removes_lock_with_dead_pid(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("4000000")
        _remove_stale_lock(lock_file)
        assert not lock_file.exists()

    def test_keeps_lock_with_alive_pid(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text(str(os.getpid()))
        _remove_stale_lock(lock_file)
        assert lock_file.exists()

    def test_removes_empty_lock_file(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("")
        _remove_stale_lock(lock_file)
        assert not lock_file.exists()

    def test_removes_malformed_lock_file(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("not-a-pid")
        _remove_stale_lock(lock_file)
        assert not lock_file.exists()

    def test_noop_when_file_missing(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        # Should not raise
        _remove_stale_lock(lock_file)


class TestWriteLock:
    def test_creates_lock_file_with_pid(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        _write_lock(lock_file)
        assert lock_file.exists()
        assert lock_file.read_text() == str(os.getpid())

    def test_raises_if_lock_file_exists(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        _write_lock(lock_file)
        with pytest.raises(FileExistsError):
            _write_lock(lock_file)

    def test_no_temp_files_left_behind(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        _write_lock(lock_file)
        # Only the lock file should exist — no temp files
        files = list(tmp_path.iterdir())
        assert files == [lock_file]

    def test_no_temp_files_on_failure(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        _write_lock(lock_file)
        with pytest.raises(FileExistsError):
            _write_lock(lock_file)
        # Only the original lock file should exist
        files = list(tmp_path.iterdir())
        assert files == [lock_file]


class TestFileLock:
    def test_acquire_creates_lock_file(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock = FileLock(lock_file)
        lock.acquire()
        assert lock_file.exists()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    def test_release_removes_lock_file(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock = FileLock(lock_file)
        lock.acquire()
        lock.release()
        assert not lock_file.exists()

    def test_release_is_idempotent(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock = FileLock(lock_file)
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise

    def test_context_manager(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        with FileLock(lock_file) as lock:
            assert lock_file.exists()
            assert isinstance(lock, FileLock)
        assert not lock_file.exists()

    def test_timeout_raises(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        # Create a lock held by "this process" so it won't be detected
        # as stale.
        lock1 = FileLock(lock_file)
        lock1.acquire()
        lock2 = FileLock(lock_file, timeout=0.2, poll_interval=0.05)
        with pytest.raises(TimeoutError, match="Failed to acquire lock"):
            lock2.acquire()
        lock1.release()

    def test_acquire_waits_for_release(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock1 = FileLock(lock_file, timeout=5)
        lock2 = FileLock(lock_file, timeout=5)
        lock1.acquire()

        acquired = threading.Event()

        def acquire_in_thread():
            lock2.acquire()
            acquired.set()
            lock2.release()

        thread = threading.Thread(target=acquire_in_thread)
        thread.start()

        # lock2 should be blocked
        assert not acquired.wait(0.2)
        lock1.release()
        # Now lock2 should acquire
        assert acquired.wait(2)
        thread.join()

    def test_stale_lock_from_dead_process_is_recovered(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        # Simulate a stale lock from a dead process
        lock_file.write_text("4000000")

        lock = FileLock(lock_file, timeout=2)
        lock.acquire()  # Should recover the stale lock and acquire
        assert lock_file.exists()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    def test_stale_empty_lock_file_is_recovered(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("")

        lock = FileLock(lock_file, timeout=2)
        lock.acquire()  # Should treat empty file as stale
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    def test_stale_malformed_lock_file_is_recovered(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("not-a-pid")

        lock = FileLock(lock_file, timeout=2)
        lock.acquire()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()


class TestFileLockAsync:
    async def test_aacquire_creates_lock_file(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock = FileLock(lock_file)
        await lock.aacquire()
        assert lock_file.exists()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    async def test_aacquire_timeout_raises(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock1 = FileLock(lock_file)
        lock1.acquire()
        lock2 = FileLock(lock_file, timeout=0.2, poll_interval=0.05)
        with pytest.raises(TimeoutError, match="Failed to acquire lock"):
            await lock2.aacquire()
        lock1.release()

    async def test_aacquire_waits_for_release(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock1 = FileLock(lock_file, timeout=5)
        lock2 = FileLock(lock_file, timeout=5)
        await lock1.aacquire()

        acquired = asyncio.Event()

        async def acquire_other():
            await lock2.aacquire()
            acquired.set()
            lock2.release()

        task = asyncio.create_task(acquire_other())
        await asyncio.sleep(0.2)
        assert not acquired.is_set()
        lock1.release()
        await asyncio.wait_for(acquired.wait(), timeout=2)
        await task

    async def test_aacquire_recovers_stale_lock(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("4000000")

        lock = FileLock(lock_file, timeout=2)
        await lock.aacquire()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    async def test_aacquire_recovers_empty_lock(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("")

        lock = FileLock(lock_file, timeout=2)
        await lock.aacquire()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()

    async def test_aacquire_recovers_malformed_lock(self, tmp_path: Path):
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("not-a-pid")

        lock = FileLock(lock_file, timeout=2)
        await lock.aacquire()
        assert lock_file.read_text() == str(os.getpid())
        lock.release()
