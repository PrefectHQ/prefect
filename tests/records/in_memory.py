import threading
from time import sleep
from uuid import uuid4

import pytest

from prefect.records.in_memory import MemoryTransactionRecord


class TestInMemoryTransactionRecord:
    def test_acquire_lock(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock()
        assert record.is_locked
        record.release_lock()
        assert not record.is_locked

    def test_acquire_lock_idempotent(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock()
        assert record.acquire_lock()
        assert record.is_locked
        record.release_lock()
        assert not record.is_locked

    def test_acquire_lock_with_hold_timeout(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock(hold_timeout=0.1)
        assert record.is_locked
        sleep(0.2)
        assert not record.is_locked

    def test_acquire_lock_with_acquire_timeout(self):
        key = str(uuid4())
        record = MemoryTransactionRecord(key=key)
        assert record.acquire_lock(holder="holder1")
        assert record.is_locked
        assert not record.acquire_lock(holder="holder2", acquire_timeout=0.1)
        record.release_lock(holder="holder1")
        assert not record.is_locked

    def test_acquire_lock_when_previously_holder_timed_out(self):
        key = str(uuid4())
        record = MemoryTransactionRecord(key=key)
        assert record.acquire_lock(holder="holder1", hold_timeout=0.1)
        assert record.is_locked
        # blocks and acquires the lock
        assert record.acquire_lock(holder="holder2")
        assert record.is_locked
        record.release_lock(holder="holder2")
        assert not record.is_locked

    def test_raises_if_releasing_with_wrong_holder(self):
        key = str(uuid4())
        record = MemoryTransactionRecord(key=key)
        assert record.acquire_lock(holder="holder1")
        assert record.is_locked
        with pytest.raises(
            ValueError, match=f"No lock held by holder2 for transaction with key {key}"
        ):
            record.release_lock(holder="holder2")

    def test_lock(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        with record.lock():
            assert record.is_locked
        assert not record.is_locked

    def test_wait_for_lock(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock(holder="holder1", hold_timeout=0.1)
        assert record.is_locked
        assert record.wait_for_lock()
        assert not record.is_locked

    def test_wait_for_lock_with_timeout(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock(holder="holder1")
        assert record.is_locked
        assert not record.wait_for_lock(timeout=0.1)
        assert record.is_locked
        record.release_lock(holder="holder1")
        assert not record.is_locked

    def test_wait_for_lock_never_been_locked(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert not record.is_locked
        assert record.wait_for_lock()

    def test_locking_works_across_threads(self):
        record = MemoryTransactionRecord(key=str(uuid4()))
        assert record.acquire_lock()
        assert record.is_locked

        def get_lock():
            assert record.acquire_lock()
            assert record.is_locked

        thread = threading.Thread(target=get_lock)
        thread.start()

        record.release_lock()
        thread.join()

        # the lock should have been acquired by the thread
        assert record.is_locked
