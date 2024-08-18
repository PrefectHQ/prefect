import pytest

from prefect.exceptions import ConfigurationError
from prefect.records.base import get_default_record_store
from prefect.records.filesystem import FileSystemRecordStore
from prefect.records.memory import MemoryRecordStore
from prefect.records.result_store import ResultFactoryStore
from prefect.settings import PREFECT_DEFAULT_RECORD_STORE, temporary_settings


class TestGetDefaultRecordStore:
    def test_out_of_the_box(self):
        store = get_default_record_store()
        assert isinstance(store, ResultFactoryStore)

    def test_with_non_default_store(self):
        with temporary_settings(
            {
                PREFECT_DEFAULT_RECORD_STORE: {
                    "fully_qualified_name": "prefect.records.memory.MemoryRecordStore",
                }
            }
        ):
            store = get_default_record_store()
            assert isinstance(store, MemoryRecordStore)

    def test_passes_through_init_kwargs(self):
        with temporary_settings(
            {
                PREFECT_DEFAULT_RECORD_STORE: {
                    "fully_qualified_name": "prefect.records.filesystem.FileSystemRecordStore",
                    "init_kwargs": {"records_directory": "/tmp/prefect/records"},
                }
            }
        ):
            store = get_default_record_store()
            assert isinstance(store, FileSystemRecordStore)
            assert store.records_directory == "/tmp/prefect/records"

    def test_raises_on_import_error(self):
        with temporary_settings(
            {
                PREFECT_DEFAULT_RECORD_STORE: {
                    "fully_qualified_name": "not.a.real.thing",
                }
            }
        ):
            with pytest.raises(
                ConfigurationError,
                match="Could not import record store class with fully qualified name",
            ):
                get_default_record_store()

    def test_raises_on_mismatched_kwargs(self):
        with temporary_settings(
            {
                PREFECT_DEFAULT_RECORD_STORE: {
                    "fully_qualified_name": "prefect.records.filesystem.FileSystemRecordStore",
                    "init_kwargs": {"not_a_real_kwarg": "foo"},
                }
            }
        ):
            with pytest.raises(
                ConfigurationError,
                match="Could not initialize default record store with provided init kwargs.",
            ):
                get_default_record_store()
