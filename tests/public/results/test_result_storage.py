import uuid
from pathlib import Path
from unittest.mock import patch

import anyio
import pytest
from sqlalchemy import delete

from prefect import flow, task
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultStore
from prefect.server.database.orm_models import (
    BlockDocument,
    BlockSchema,
    BlockSchemaReference,
    BlockType,
)


async def _custom_awrite_path(self, path: str, content: bytes) -> str:
    """Custom async write method for testing that awrite_path is called in async context."""
    _path: Path = self._resolve_path(path)

    _path.parent.mkdir(exist_ok=True, parents=True)

    if _path.exists() and not _path.is_file():
        raise ValueError(f"Path {_path} already exists and is not a file.")

    async with await anyio.open_file(_path, mode="wb") as f:
        await f.write(content)
    return str(_path)


@pytest.fixture
async def custom_storage_block(tmpdir: Path, db):
    """
    Create a custom storage block for testing async write methods.

    Uses type() to create a dynamically-named class to avoid Block registry conflicts.
    Cleans up BlockType, BlockSchema, and BlockDocument records after the test to
    prevent conflicts with other tests excluded from clear_db (like tests/results).
    """
    unique_id = uuid.uuid4().hex[:8]
    unique_slug = f"test-storage-{unique_id}"
    doc_name = f"test-{unique_id}"

    # Create a dynamically-named class to avoid Block registry conflicts
    CustomStorage = type(
        f"CustomStorage{unique_id}",
        (LocalFileSystem,),
        {
            "_block_type_slug": unique_slug,
            "awrite_path": _custom_awrite_path,
        },
    )

    test = CustomStorage(basepath=str(tmpdir))
    await test.save(doc_name, overwrite=True)

    yield test

    # Clean up database records to prevent conflicts with other tests
    async with db.session_context() as session:
        # Delete BlockDocument first (references BlockSchema)
        await session.execute(
            delete(BlockDocument).where(BlockDocument.name == doc_name)
        )
        # Delete BlockSchemaReference (references BlockSchema)
        block_type_result = await session.execute(
            BlockType.__table__.select().where(BlockType.slug == unique_slug)
        )
        block_type_row = block_type_result.first()
        if block_type_row:
            await session.execute(
                delete(BlockSchemaReference).where(
                    BlockSchemaReference.parent_block_schema_id.in_(
                        BlockSchema.__table__.select()
                        .where(BlockSchema.block_type_id == block_type_row.id)
                        .with_only_columns(BlockSchema.id)
                    )
                )
            )
            # Delete BlockSchema (references BlockType)
            await session.execute(
                delete(BlockSchema).where(
                    BlockSchema.block_type_id == block_type_row.id
                )
            )
            # Delete BlockType
            await session.execute(
                delete(BlockType).where(BlockType.slug == unique_slug)
            )
        await session.commit()


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
