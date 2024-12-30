from pathlib import Path
from unittest.mock import patch

import anyio
import pytest

from prefect import flow, task
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultStore


@pytest.fixture
def custom_storage_block(tmpdir: Path):
    class Test(LocalFileSystem):
        _block_type_slug = "test"

        async def awrite_path(self, path: str, content: bytes) -> str:
            _path: Path = self._resolve_path(path)

            _path.parent.mkdir(exist_ok=True, parents=True)

            if _path.exists() and not _path.is_file():
                raise ValueError(f"Path {_path} already exists and is not a file.")

            async with await anyio.open_file(_path, mode="wb") as f:
                await f.write(content)
            return str(_path)

    Test.register_type_and_schema()
    test = Test(basepath=str(tmpdir))
    test.save("test", overwrite=True)
    return test


async def test_async_method_used_in_async_context(
    custom_storage_block: LocalFileSystem,
):
    # this is a regression test for https://github.com/PrefectHQ/prefect/issues/16486
    with patch.object(
        custom_storage_block, "awrite_path", wraps=custom_storage_block.awrite_path
    ) as mock_awrite:

        @task(result_storage=custom_storage_block, result_storage_key="testing")
        async def t():
            return "this is a test"

        @flow
        async def f():
            return await t()

        result = await f()
        assert result == "this is a test"
        store = ResultStore(result_storage=custom_storage_block)
        stored_result_record = await store.aread("testing")

        assert stored_result_record.result == result == "this is a test"
        # Verify awrite_path was called
        mock_awrite.assert_awaited_once()
        assert mock_awrite.await_args[0][0] == "testing"  # Check path argument
