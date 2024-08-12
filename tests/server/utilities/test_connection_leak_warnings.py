"""
This test suite exists to reproduce the issue in
https://github.com/PrefectHQ/prefect/issues/11820

They shouldn't be run as part of the normal test suite, but can be run manually with:

TEST_CONNECTION_LEAK=true pytest tests/server/utilities/test_connection_leak_warnings.py
"""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_CONNECTION_LEAK"),
    reason="Skipping connection leak tests",
)


async def test_direct_connection_leak(database_engine: AsyncEngine):
    connection = await database_engine.connect()
    await connection.get_raw_connection()
    # don't close the connection


async def test_leaking_connection_via_engine(database_engine: AsyncEngine):
    connection = await database_engine.connect()
    await connection.execute(sa.text("SELECT 1"))
    # don't close the connection


async def test_leaking_connection_via_session(database_engine: AsyncEngine):
    session = AsyncSession(database_engine)
    await session.execute(sa.text("SELECT 1"))
    # don't close the session
