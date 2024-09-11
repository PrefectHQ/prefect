import queue
import threading
from time import sleep
from uuid import uuid4

import pytest

from prefect.locking.filesystem import FileSystemLockManager
from prefect.locking.memory import MemoryLockManager
from prefect.results import ResultStore


class TestMemoryLockManager:
    def test_singleton(self):
        manager1 = MemoryLockManager()
        manager2 = MemoryLockManager()
        assert manager1 is manager2

    async def test_read_locked_key(self):
        key = str(uuid4())
        store = ResultStore(lock_manager=MemoryLockManager())
        read_queue = queue.Queue()

        def read_locked_key():
            record = store.read(key)
            read_queue.put(record.result)

        thread = threading.Thread(target=read_locked_key)
        assert store.acquire_lock(key, holder="holder1")
        thread.start()
        await store.awrite(key=key, obj={"test": "value"}, holder="holder1")
        store.release_lock(key, holder="holder1")
        thread.join()
        # the read should have been blocked until the lock was released
        assert read_queue.get_nowait() == {"test": "value"}

    async def test_write_to_key_with_same_lock_holder(self):
        key = str(uuid4())
        store = ResultStore(lock_manager=MemoryLockManager())
        assert store.acquire_lock(key)
        # can write to key because holder is the same
        store.write(key=key, obj={"test": "value"})
        assert (record := store.read(key)) is not None
        assert record.result == {"test": "value"}

    async def test_write_to_key_with_different_lock_holder(self):
        key = str(uuid4())
        store = ResultStore(lock_manager=MemoryLockManager())
        assert store.acquire_lock(key, holder="holder1")
        with pytest.raises(
            RuntimeError,
            match=f"Cannot write to result record with key {key} because it is locked by another holder.",
        ):
            store.write(key=key, obj={"test": "value"}, holder="holder2")

    def test_acquire_lock(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.is_locked(key)
        manager.release_lock(key, holder="holder1")
        assert not manager.is_locked(key)

    def test_acquire_lock_idempotent(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.is_locked(key)
        manager.release_lock(key, holder="holder1")
        assert not manager.is_locked(key)

    def test_acquire_lock_with_hold_timeout(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert manager.is_locked(key)
        sleep(0.2)
        assert not manager.is_locked(key)

    def test_acquire_lock_with_acquire_timeout(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key=key, holder="holder1")
        assert manager.is_locked(key)
        assert not manager.acquire_lock(key=key, holder="holder2", acquire_timeout=0.1)
        manager.release_lock(key=key, holder="holder1")
        assert not manager.is_locked(key=key)

    def test_acquire_lock_when_previously_holder_timed_out(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert manager.is_locked(key=key)
        # blocks and acquires the lock
        assert manager.acquire_lock(key=key, holder="holder2")
        assert manager.is_locked(key=key)
        manager.release_lock(key=key, holder="holder2")
        assert not manager.is_locked(key=key)

    def test_raises_if_releasing_with_wrong_holder(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key=key, holder="holder1")
        assert manager.is_locked(key=key)
        with pytest.raises(
            ValueError, match=f"No lock held by holder2 for transaction with key {key}"
        ):
            manager.release_lock(key=key, holder="holder2")

    def test_is_lock_holder(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert not manager.is_lock_holder(key, holder="holder1")
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.is_lock_holder(key, holder="holder1")
        assert not manager.is_lock_holder(key, holder="holder2")

    def test_wait_for_lock(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key, holder="holder1", hold_timeout=0.1)
        assert manager.is_locked(key)
        assert manager.wait_for_lock(key)
        assert not manager.is_locked(key)

    def test_wait_for_lock_with_timeout(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.is_locked(key)
        assert not manager.wait_for_lock(key, timeout=0.1)
        assert manager.is_locked(key)
        manager.release_lock(key, holder="holder1")
        assert not manager.is_locked(key)

    def test_wait_for_lock_never_been_locked(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert not manager.is_locked(key)
        assert manager.wait_for_lock(key)

    def test_locking_works_across_threads(self):
        key = str(uuid4())
        manager = MemoryLockManager()
        assert manager.acquire_lock(key, holder="holder1")
        assert manager.is_locked(key)

        def get_lock():
            assert manager.acquire_lock(key, holder="holder2")
            assert manager.is_locked(key)

        thread = threading.Thread(target=get_lock)
        thread.start()

        manager.release_lock(key, holder="holder1")
        thread.join()

        # the lock should have been acquired by the thread
        assert manager.is_locked(key)


class TestFileSystemLockManager:
    @pytest.fixture
    def store(self, tmp_path):
        return FileSystemLockManager(lock_files_directory=tmp_path)

    async def test_read_locked_key(self, store):
        key = str(uuid4())
        store = ResultStore(lock_manager=store)
        read_queue = queue.Queue()

        def read_locked_key():
            record = store.read(key)
            read_queue.put(record.result)

        thread = threading.Thread(target=read_locked_key)
        assert store.acquire_lock(key, holder="holder1")
        thread.start()
        await store.awrite(key=key, obj={"test": "value"}, holder="holder1")
        store.release_lock(key, holder="holder1")
        thread.join()
        # the read should have been blocked until the lock was released
        assert read_queue.get_nowait() == {"test": "value"}

    async def test_write_to_key_with_same_lock_holder(self, store):
        key = str(uuid4())
        store = ResultStore(lock_manager=store)
        assert store.acquire_lock(key)
        # can write to key because holder is the same
        store.write(key=key, obj={"test": "value"})
        assert (record := store.read(key)) is not None
        assert record.result == {"test": "value"}

    async def test_write_to_key_with_different_lock_holder(self, store):
        key = str(uuid4())
        store = ResultStore(lock_manager=store)
        assert store.acquire_lock(key, holder="holder1")
        with pytest.raises(
            RuntimeError,
            match=f"Cannot write to result record with key {key} because it is locked by another holder.",
        ):
            store.write(key=key, obj={"test": "value"}, holder="holder2")

    def test_acquire_lock(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    async def test_acquire_lock_async(self, store):
        key = str(uuid4())
        assert await store.aacquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    def test_acquire_lock_idempotent(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    def test_acquire_lock_with_hold_timeout(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert store.is_locked(key)
        sleep(0.2)
        assert not store.is_locked(key)

    def test_acquire_lock_with_acquire_timeout(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key=key, holder="holder1")
        assert store.is_locked(key)
        assert not store.acquire_lock(key=key, holder="holder2", acquire_timeout=0.1)
        store.release_lock(key=key, holder="holder1")
        assert not store.is_locked(key=key)

    def test_acquire_lock_when_previously_holder_timed_out(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert store.is_locked(key=key)
        # blocks and acquires the lock
        assert store.acquire_lock(key=key, holder="holder2")
        assert store.is_locked(key=key)
        store.release_lock(key=key, holder="holder2")
        assert not store.is_locked(key=key)

    def test_raises_if_releasing_with_wrong_holder(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key=key, holder="holder1")
        assert store.is_locked(key=key)
        with pytest.raises(
            ValueError, match=f"No lock held by holder2 for transaction with key {key}"
        ):
            store.release_lock(key=key, holder="holder2")

    def test_is_lock_holder(self, store):
        key = str(uuid4())
        assert not store.is_lock_holder(key, holder="holder1")
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_lock_holder(key, holder="holder1")
        assert not store.is_lock_holder(key, holder="holder2")

    def test_wait_for_lock(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1", hold_timeout=0.1)
        assert store.is_locked(key)
        assert store.wait_for_lock(key)
        assert not store.is_locked(key)

    def test_wait_for_lock_with_timeout(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        assert not store.wait_for_lock(key, timeout=0.1)
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    def test_wait_for_lock_never_been_locked(self, store):
        key = str(uuid4())
        assert not store.is_locked(key)
        assert store.wait_for_lock(key)

    async def test_wait_for_lock_async(self, store):
        key = str(uuid4())
        assert await store.aacquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        assert not await store.await_for_lock(key, timeout=0.1)
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    async def test_wait_for_lock_async_with_timeout(self, store):
        key = str(uuid4())
        assert await store.aacquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        assert not await store.await_for_lock(key, timeout=0.1)
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    async def test_wait_for_lock_async_never_been_locked(self, store):
        key = str(uuid4())
        assert not store.is_locked(key)
        assert await store.await_for_lock(key)

    def test_locking_works_across_threads(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_locked(key)

        def get_lock():
            assert store.acquire_lock(key, holder="holder2")
            assert store.is_locked(key)

        thread = threading.Thread(target=get_lock)
        thread.start()

        store.release_lock(key, holder="holder1")
        thread.join()

        # the lock should have been acquired by the thread
        assert store.is_locked(key)
