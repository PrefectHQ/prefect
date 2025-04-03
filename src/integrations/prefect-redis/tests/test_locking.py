import queue
import threading
import time
from uuid import uuid4

import pytest
from prefect_redis.blocks import RedisDatabase
from prefect_redis.locking import RedisLockManager

from prefect.results import ResultStore


class TestRedisLockManager:
    @pytest.fixture
    def lock_manager(self):
        return RedisLockManager()

    @pytest.fixture
    def store(self, lock_manager):
        return ResultStore(lock_manager=lock_manager)

    def test_init(self):
        store = RedisLockManager(
            host="host",
            port=1234,
            db=1,
            username="username",
            password="password",
            ssl=True,
        )
        assert store.host == "host"
        assert store.port == 1234
        assert store.db == 1
        assert store.username == "username"
        assert store.password == "password"
        assert store.ssl

    def test_read_locked_key(self, store):
        key = str(uuid4())
        read_queue = queue.Queue()
        thread_started = threading.Event()

        def read_locked_key():
            thread_started.set()

            # This read should block until the lock is released
            record = store.read(key)
            assert record is not None
            read_queue.put(record.result, block=False)

        thread = threading.Thread(target=read_locked_key)

        assert store.acquire_lock(key, holder="holder1")

        thread.start()
        thread_started.wait()

        store.write(key=key, obj={"test": "value"}, holder="holder1")
        store.release_lock(key, holder="holder1")

        # the read should have been blocked until the lock was released
        assert read_queue.get(timeout=10) == {"test": "value"}
        thread.join()

    def test_write_to_key_with_same_lock_holder(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key)
        # can write to key because holder is the same
        store.write(key=key, obj={"test": "value"})
        assert (record := store.read(key)) is not None
        assert record.result == {"test": "value"}

    def test_write_to_key_with_different_lock_holder(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        with pytest.raises(
            RuntimeError,
            match=f"Cannot write to result record with key {key} because it is locked by another holder.",
        ):
            store.write(key=key, obj={"test": "value"}, holder="holder2")

    def test_acquire_lock(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.is_locked(key)
        lock_manager.release_lock(key, holder="holder1")
        assert not lock_manager.is_locked(key)

    def test_acquire_lock_idempotent(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.is_locked(key)
        lock_manager.release_lock(key, holder="holder1")
        assert not lock_manager.is_locked(key)

    def test_acquire_lock_with_hold_timeout(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert lock_manager.is_locked(key)
        time.sleep(0.2)
        assert not lock_manager.is_locked(key)

    def test_acquire_lock_with_acquire_timeout(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key=key, holder="holder1")
        assert lock_manager.is_locked(key)
        assert not lock_manager.acquire_lock(
            key=key, holder="holder2", acquire_timeout=0.1
        )
        lock_manager.release_lock(key=key, holder="holder1")
        assert not lock_manager.is_locked(key=key)

    def test_acquire_lock_when_previously_holder_timed_out(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key=key, holder="holder1", hold_timeout=0.1)
        assert lock_manager.is_locked(key=key)
        # blocks and acquires the lock
        assert lock_manager.acquire_lock(key=key, holder="holder2")
        assert lock_manager.is_locked(key=key)
        lock_manager.release_lock(key=key, holder="holder2")
        assert not lock_manager.is_locked(key=key)

    def test_raises_if_releasing_with_wrong_holder(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key=key, holder="holder1")
        assert lock_manager.is_locked(key=key)
        with pytest.raises(
            ValueError, match=f"No lock held by holder2 for transaction with key {key}"
        ):
            lock_manager.release_lock(key=key, holder="holder2")

    def test_is_lock_holder(self, lock_manager):
        key = str(uuid4())
        assert not lock_manager.is_lock_holder(key, holder="holder1")
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.is_lock_holder(key, holder="holder1")
        assert not lock_manager.is_lock_holder(key, holder="holder2")

    def test_wait_for_lock(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key, holder="holder1", hold_timeout=1)
        assert lock_manager.is_locked(key)
        assert lock_manager.wait_for_lock(key)
        assert not lock_manager.is_locked(key)

    def test_wait_for_lock_with_timeout(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.is_locked(key)
        assert not lock_manager.wait_for_lock(key, timeout=0.1)
        assert lock_manager.is_locked(key)
        lock_manager.release_lock(key, holder="holder1")
        assert not lock_manager.is_locked(key)

    def test_wait_for_lock_never_been_locked(self, lock_manager):
        key = str(uuid4())
        assert not lock_manager.is_locked(key)
        assert lock_manager.wait_for_lock(key)

    def test_locking_works_across_threads(self, lock_manager):
        key = str(uuid4())
        assert lock_manager.acquire_lock(key, holder="holder1")
        assert lock_manager.is_locked(key)

        def get_lock():
            assert lock_manager.acquire_lock(key, holder="holder2")
            assert lock_manager.is_locked(key)

        thread = threading.Thread(target=get_lock)
        thread.start()

        lock_manager.release_lock(key, holder="holder1")
        thread.join()

        # the lock should have been acquired by the thread
        assert lock_manager.is_locked(key)

    def test_configure_from_block(self):
        block = RedisDatabase(
            host="host",
            port=1234,
            db=1,
            username="username",
            password="password",
            ssl=True,
        )
        lock_manager = RedisLockManager(**block.as_connection_params())
        assert lock_manager.host == "host"
        assert lock_manager.port == 1234
        assert lock_manager.db == 1
        assert lock_manager.username == "username"
        assert lock_manager.password == "password"
        assert lock_manager.ssl

    def test_release_lock_with_nonexistent_lock(self, lock_manager):
        # Test the fix for issue #17676
        key = str(uuid4())

        # Simulate a scenario where a lock is acquired and released during rollback
        assert lock_manager.acquire_lock(key=key, holder="holder1")
        assert lock_manager.is_locked(key)
        lock_manager.release_lock(key=key, holder="holder1")
        assert not lock_manager.is_locked(key)

        # Now try to release a lock that doesn't exist anymore
        # This should not raise an error
        lock_manager.release_lock(key=key, holder="holder1")

        # Now simulate a retry case: acquire with new holder, then try to release with old
        assert lock_manager.acquire_lock(key=key, holder="holder2")
        assert lock_manager.is_locked(key)

        # Verify that trying to release with wrong holder correctly fails
        with pytest.raises(
            ValueError, match=f"No lock held by holder1 for transaction with key {key}"
        ):
            lock_manager.release_lock(key=key, holder="holder1")

        # But if the lock doesn't exist in Redis, it should succeed
        # (first release it properly)
        lock_manager.release_lock(key=key, holder="holder2")
        assert not lock_manager.is_locked(key)
        # Then try to release with wrong holder - should not raise
        lock_manager.release_lock(key=key, holder="holder1")

    async def test_transaction_retry_lock_behavior(self, lock_manager):
        """Test that simulates the exact behavior during transaction retries (issue #17676)"""
        key = str(uuid4())
        store = ResultStore(lock_manager=lock_manager)

        # 1. First transaction acquires a lock
        assert store.acquire_lock(key, holder="transaction1")

        # 2. Transaction rollback happens, which releases the lock
        store.release_lock(key, holder="transaction1")
        assert not lock_manager.is_locked(key)

        # 3. Task retries, transaction is recreated with a new holder ID
        assert store.acquire_lock(key, holder="transaction2")

        # 4. Transaction succeeds and tries to commit
        # For testing, we manually verify both behaviors:

        # 4a. If trying to release with original holder, it would fail
        # BUT thanks to our fix, it will NOT fail if the lock is missing
        with pytest.raises(ValueError):
            # This should fail because we have a real conflict - different holder
            store.release_lock(key, holder="transaction1")

        # Release the lock properly
        store.release_lock(key, holder="transaction2")

        # 4b. Now simulate the "release after rollback" case - SHOULD NOT raise
        # This is what our fix specifically addresses
        store.release_lock(key, holder="transaction1")
