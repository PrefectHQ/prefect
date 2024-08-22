import queue
import threading
import time
from uuid import uuid4

import pendulum
import pytest
from prefect_redis.records import RedisRecordStore

from prefect.filesystems import LocalFileSystem
from prefect.results import ResultFactory
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    temporary_settings,
)
from prefect.transactions import IsolationLevel


class TestRedisRecordStore:
    @pytest.fixture()
    def default_storage_setting(self, tmp_path):
        name = str(uuid4())
        LocalFileSystem(basepath=tmp_path).save(name)
        with temporary_settings(
            {
                PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: f"local-file-system/{name}",
            }
        ):
            yield

    @pytest.fixture
    async def result(self, default_storage_setting):
        factory = await ResultFactory.default_factory(
            persist_result=True,
        )
        result = await factory.create_result(obj={"test": "value"})
        return result

    @pytest.fixture
    def store(self):
        return RedisRecordStore()

    def test_init(self):
        store = RedisRecordStore(
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

    def test_read_write(self, store, result):
        key = str(uuid4())
        assert store.read(key) is None
        store.write(key, result=result)
        assert (record := store.read(key)) is not None
        assert record.key == key
        assert record.result == result

    def test_read_locked_key(self, store, result):
        key = str(uuid4())
        read_queue = queue.Queue()

        def read_locked_key():
            record = store.read(key)
            assert record is not None
            read_queue.put(record.result, block=False)

        thread = threading.Thread(
            target=read_locked_key,
        )
        assert store.acquire_lock(key, holder="holder1")
        thread.start()
        store.write(key, result=result, holder="holder1")
        store.release_lock(key, holder="holder1")
        # the read should have been blocked until the lock was released
        assert read_queue.get(timeout=10) == result
        thread.join()

    def test_write_to_key_with_same_lock_holder(self, store, result):
        key = str(uuid4())
        assert store.acquire_lock(key)
        # can write to key because holder is the same
        store.write(key, result=result)
        assert (record := store.read(key)) is not None
        assert record.result == result

    def test_write_to_key_with_different_lock_holder(self, store, result):
        key = str(uuid4())
        assert store.acquire_lock(key, holder="holder1")
        with pytest.raises(
            ValueError,
            match=f"Cannot write to transaction with key {key} because it is locked by another holder.",
        ):
            store.write(key, result=result, holder="holder2")

    def test_exists(self, store, result):
        key = str(uuid4())
        assert not store.exists(key)
        store.write(key, result=result)
        assert store.exists(key)

    def test_exists_with_expired_result(self, store, result):
        key = str(uuid4())
        result.expiration = pendulum.now().add(seconds=1)
        store.write(key, result=result)
        assert store.exists(key)
        time.sleep(2)
        assert not store.exists(key)

    def test_acquire_lock(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key)
        assert store.is_locked(key)
        store.release_lock(key)
        assert not store.is_locked(key)

    def test_acquire_lock_idempotent(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key)
        assert store.acquire_lock(key)
        assert store.is_locked(key)
        store.release_lock(key)
        assert not store.is_locked(key)

    def test_acquire_lock_with_hold_timeout(self, store):
        key = str(uuid4())
        assert store.acquire_lock(key=key, hold_timeout=0.1)
        assert store.is_locked(key)
        time.sleep(0.2)
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
        assert store.acquire_lock(key, holder="holder1", hold_timeout=1)
        assert store.is_locked(key)
        assert store.wait_for_lock(key)
        assert not store.is_locked(key)

    def test_lock(self, store):
        key = str(uuid4())
        with store.lock(key):
            assert store.is_locked(key)
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

    def test_locking_works_across_threads(self, store):
        key = str(uuid4())
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

    def test_supports_serialization_level(self, store):
        assert store.supports_isolation_level(IsolationLevel.READ_COMMITTED)
        assert store.supports_isolation_level(IsolationLevel.SERIALIZABLE)
        assert not store.supports_isolation_level("UNKNOWN")
