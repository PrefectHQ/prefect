"""
Fixtures for tests/results/ module.

This module is excluded from the clear_db auto-mark, meaning the database is not
cleared before each test. To prevent tests from encountering block documents
created by other tests (which may reference unregistered block types), we clear
block-related tables before each test in this module.
"""

import pytest

from prefect.server.database import orm_models


@pytest.fixture(autouse=True)
async def clear_block_documents(db):
    """
    Clear block documents before each test to prevent conflicts with block
    documents created by other tests that may reference unregistered block types.

    This is necessary because tests/results is excluded from the clear_db
    auto-mark, so the database is shared with other tests. Other tests may
    create custom block types (like tests/blocks/test_core.py or
    tests/public/results/test_result_storage.py) that aren't registered in
    this module's environment.
    """
    async with db.session_context(begin_transaction=True) as session:
        await session.execute(orm_models.BlockDocument.__table__.delete())
        await session.execute(orm_models.BlockSchema.__table__.delete())
        await session.execute(orm_models.BlockType.__table__.delete())
        await session.execute(orm_models.BlockSchemaReference.__table__.delete())

    yield
