from pathlib import Path

import pytest

from prefect.records.filesystem import FileSystemRecordStore
from prefect.records.memory import MemoryRecordStore
from prefect.records.result_store import ResultRecordStore
from prefect.results import get_result_store


def test_all_result_stores_emit_deprecation_warning():
    with pytest.warns(DeprecationWarning):
        ResultRecordStore(result_store=get_result_store())

    with pytest.warns(DeprecationWarning):
        MemoryRecordStore()

    with pytest.warns(DeprecationWarning):
        FileSystemRecordStore(records_directory=Path("foo"))
