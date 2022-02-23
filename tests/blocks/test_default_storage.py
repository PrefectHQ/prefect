import pytest

from prefect import flow, task
from prefect.blocks import storage


@pytest.fixture
def simple_flow():
    @task
    def add(x):
        return x + 1

    @flow
    def my_flow():
        add(1)

    return my_flow


async def test_local_storage_default(simple_flow):

    storage_dir = storage.TempStorageBlock().basepath() / "prefect"
    file_count = len(list(storage_dir.iterdir()))

    simple_flow()

    # assert new files were written to temp storage
    file_count_2 = len(list(storage_dir.iterdir()))
    assert file_count_2 > file_count
