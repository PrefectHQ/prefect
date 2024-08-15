from uuid import uuid4

import pytest

from prefect.filesystems import LocalFileSystem
from prefect.records.filesystem import FileSystemRecordStore
from prefect.results import ResultFactory
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    temporary_settings,
)
from prefect.transactions import IsolationLevel


class TestFileSystemRecordStore:
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
        return FileSystemRecordStore()

    def test_read_write(self, store, result):
        key = str(uuid4())
        assert store.read(key) is None
        store.write(key, result=result)
        assert (record := store.read(key)) is not None
        assert record.key == key
        assert record.result == result

    def test_exists(self, store, result):
        key = str(uuid4())
        assert not store.exists(key)
        store.write(key, result=result)
        assert store.exists(key)

    def test_acquire_lock(self):
        key = str(uuid4())
        store = FileSystemRecordStore()
        assert store.acquire_lock(key)
        assert store.is_locked(key)
        store.release_lock(key)
        assert not store.is_locked(key)

    def test_supports_serialization_level(self):
        store = FileSystemRecordStore()
        assert store.supports_isolation_level(IsolationLevel.READ_COMMITTED)
        assert store.supports_isolation_level(IsolationLevel.SERIALIZABLE)
        assert not store.supports_isolation_level("UNKNOWN")
