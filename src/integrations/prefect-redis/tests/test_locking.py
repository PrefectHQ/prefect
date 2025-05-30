import asyncio
import pickle
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

    async def test_pickle_unpickle_and_use_lock_manager(
        self, lock_manager: RedisLockManager
    ):
        """
        Tests that RedisLockManager can be pickled, unpickled, and then used successfully,
        ensuring clients are re-initialized correctly on unpickle.
        """
        # With the new __init__, clients are initialized immediately.
        # So, no initial check for them being None.

        # Store original client IDs for comparison after unpickling
        original_client_id = id(lock_manager.client)
        original_async_client_id = id(lock_manager.async_client)

        # Pickle and unpickle
        pickled_manager = pickle.dumps(lock_manager)
        unpickled_manager: RedisLockManager = pickle.loads(pickled_manager)

        # Verify state after unpickling: clients should be NEW instances due to __setstate__ calling _init_clients()
        assert unpickled_manager.client is not None, (
            "Client should be re-initialized after unpickling, not None"
        )
        assert unpickled_manager.async_client is not None, (
            "Async client should be re-initialized after unpickling, not None"
        )

        assert id(unpickled_manager.client) != original_client_id, (
            "Client should be a NEW instance after unpickling"
        )
        assert id(unpickled_manager.async_client) != original_async_client_id, (
            "Async client should be a NEW instance after unpickling"
        )

        # _locks should be an empty dict after unpickling due to __setstate__
        assert (
            hasattr(unpickled_manager, "_locks")
            and isinstance(getattr(unpickled_manager, "_locks"), dict)
            and not getattr(unpickled_manager, "_locks")
        ), "_locks should be an empty dict after unpickling"

        # Test synchronous operations (clients are already initialized)
        sync_key = "test_sync_pickle_key"
        sync_holder = "sync_pickle_holder"

        acquired_sync = unpickled_manager.acquire_lock(
            sync_key, holder=sync_holder, acquire_timeout=1, hold_timeout=5
        )
        assert acquired_sync, "Should acquire sync lock after unpickling"
        assert unpickled_manager.client is not None, (
            "Sync client should be initialized after use"
        )
        assert unpickled_manager.is_lock_holder(sync_key, sync_holder), (
            "Should be sync lock holder"
        )
        unpickled_manager.release_lock(sync_key, sync_holder)
        assert not unpickled_manager.is_locked(sync_key), "Sync lock should be released"

        # Test asynchronous operations (async_client is already initialized after unpickling)
        async_key = "test_async_pickle_key"
        async_holder = "async_pickle_holder"
        hold_timeout_seconds = 0.2  # Use a short hold timeout for testing expiration

        acquired_async = await unpickled_manager.aacquire_lock(
            async_key,
            holder=async_holder,
            acquire_timeout=1,
            hold_timeout=hold_timeout_seconds,
        )
        assert acquired_async, "Should acquire async lock after unpickling"
        assert unpickled_manager.async_client is not None, (
            "Async client should be initialized after async use"
        )

        # Verify holder by re-acquiring (should succeed as it's the same holder and lock is fresh)
        assert await unpickled_manager.aacquire_lock(
            async_key,
            holder=async_holder,
            acquire_timeout=1,
            hold_timeout=hold_timeout_seconds,
        ), "Re-acquiring same async lock should succeed"

        # Wait for the lock to expire based on hold_timeout
        await asyncio.sleep(
            hold_timeout_seconds + 0.1
        )  # Wait a bit longer than the timeout

        # Verify it's released (expired) by trying to acquire with a different holder.
        new_async_holder = "new_async_pickle_holder"
        acquired_by_new = await unpickled_manager.aacquire_lock(
            async_key,
            holder=new_async_holder,
            acquire_timeout=1,
            hold_timeout=hold_timeout_seconds,
        )
        assert acquired_by_new, (
            "Should acquire async lock with new holder after original lock expires"
        )
