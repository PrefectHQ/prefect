import queue
import threading
from time import sleep
from uuid import uuid4

import pytest

from prefect.records.memory import MemoryRecordStore
from prefect.results import ResultStore
from prefect.transactions import IsolationLevel


@pytest.fixture(autouse=True)
def ignore_deprecations(ignore_prefect_deprecation_warnings):
    """This file will be removed in a future release when MemoryRecordStore is removed."""


class TestInMemoryRecordStore:
    def test_singleton(self):
        store1 = MemoryRecordStore()
        store2 = MemoryRecordStore()
        assert store1 is store2

    async def test_read_write(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.read(key) is None
        result_store = ResultStore(persist_result=True)
        result = await result_store.create_result(obj={"test": "value"})
        store.write(key, result=result)
        assert (record := store.read(key)) is not None
        assert record.key == key
        assert record.result == result

    async def test_read_locked_key(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        result_store = ResultStore(persist_result=True)
        result = await result_store.create_result(obj={"test": "value"})

        def read_locked_key(queue):
            record = store.read(key)
            assert record is not None
            queue.put(record.result)

        thread = threading.Thread(
            target=read_locked_key, args=(read_queue := queue.Queue(),)
        )
        assert store.acquire_lock(key, holder="holder1")
        thread.start()
        store.write(key, result=result, holder="holder1")
        store.release_lock(key, holder="holder1")
        thread.join()
        # the read should have been blocked until the lock was released
        assert read_queue.get_nowait() == result

    async def test_write_to_key_with_same_lock_holder(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key)
        result_store = ResultStore(persist_result=True)
        result = await result_store.create_result(obj={"test": "value"})
        # can write to key because holder is the same
        store.write(key, result=result)
        assert (record := store.read(key)) is not None
        assert record.result == result

    async def test_write_to_key_with_different_lock_holder(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key, holder="holder1")
        result_store = ResultStore(persist_result=True)
        result = await result_store.create_result(obj={"test": "value"})
        with pytest.raises(
            ValueError,
            match=f"Cannot write to transaction with key {key} because it is locked by another holder.",
        ):
            store.write(key, result=result, holder="holder2")

    async def test_exists(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert not store.exists(key)
        result_store = ResultStore(persist_result=True)
        result = await result_store.create_result(obj={"test": "value"})
        store.write(key, result=result)
        assert store.exists(key)

    def test_acquire_lock(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key)
        assert store.is_locked(key)
        store.release_lock(key)
        assert not store.is_locked(key)

    def test_acquire_lock_idempotent(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key)
        assert store.acquire_lock(key)
        assert store.is_locked(key)
        store.release_lock(key)
        assert not store.is_locked(key)

    def test_acquire_lock_with_hold_timeout(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key=key, hold_timeout=0.1)
        assert store.is_locked(key)
        sleep(0.2)
        assert not store.is_locked(key)

    def test_acquire_lock_with_acquire_timeout(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key=key, holder="holder1")
        assert store.is_locked(key)
        assert not store.acquire_lock(key=key, holder="holder2", acquire_timeout=0.1)
        store.release_lock(key=key, holder="holder1")
        assert not store.is_locked(key=key)

    def test_acquire_lock_when_previously_holder_timed_out(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert store.is_locked(key=key)
        # blocks and acquires the lock
        assert store.acquire_lock(key=key, holder="holder2")
        assert store.is_locked(key=key)
        store.release_lock(key=key, holder="holder2")
        assert not store.is_locked(key=key)

    def test_raises_if_releasing_with_wrong_holder(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key=key, holder="holder1")
        assert store.is_locked(key=key)
        with pytest.raises(
            ValueError, match=f"No lock held by holder2 for transaction with key {key}"
        ):
            store.release_lock(key=key, holder="holder2")

    def test_lock(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        with store.lock(key):
            assert store.is_locked(key)
        assert not store.is_locked(key)

    def test_is_lock_holder(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert not store.is_lock_holder(key, holder="holder1")
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_lock_holder(key, holder="holder1")
        assert not store.is_lock_holder(key, holder="holder2")

    def test_wait_for_lock(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key, holder="holder1", hold_timeout=0.1)
        assert store.is_locked(key)
        assert store.wait_for_lock(key)
        assert not store.is_locked(key)

    def test_wait_for_lock_with_timeout(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key, holder="holder1")
        assert store.is_locked(key)
        assert not store.wait_for_lock(key, timeout=0.1)
        assert store.is_locked(key)
        store.release_lock(key, holder="holder1")
        assert not store.is_locked(key)

    def test_wait_for_lock_never_been_locked(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert not store.is_locked(key)
        assert store.wait_for_lock(key)

    def test_locking_works_across_threads(self):
        key = str(uuid4())
        store = MemoryRecordStore()
        assert store.acquire_lock(key)
        assert store.is_locked(key)

        def get_lock():
            assert store.acquire_lock(key)
            assert store.is_locked(key)

        thread = threading.Thread(target=get_lock)
        thread.start()

        store.release_lock(key)
        thread.join()

        # the lock should have been acquired by the thread
        assert store.is_locked

    def test_supports_serialization_level(self):
        store = MemoryRecordStore()
        assert store.supports_isolation_level(IsolationLevel.READ_COMMITTED)
        assert store.supports_isolation_level(IsolationLevel.SERIALIZABLE)
        assert not store.supports_isolation_level("UNKNOWN")
