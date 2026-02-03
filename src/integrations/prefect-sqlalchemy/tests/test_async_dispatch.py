"""Tests for the SqlAlchemyConnector class split.

These tests verify that SqlAlchemyConnector (sync) and AsyncSqlAlchemyConnector (async)
work correctly with their respective driver types.
"""

from typing import Coroutine

import pytest
from prefect_sqlalchemy.credentials import (
    AsyncDriver,
    ConnectionComponents,
    SyncDriver,
)
from prefect_sqlalchemy.database import AsyncSqlAlchemyConnector, SqlAlchemyConnector
from sqlalchemy.engine.cursor import CursorResult

from prefect import flow


class TestSqlAlchemyConnectorSync:
    """Tests for SqlAlchemyConnector with sync drivers."""

    def test_fetch_one_sync_context_returns_value_not_coroutine(self, tmp_path):
        """fetch_one must return tuple (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                connector.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
                result = connector.fetch_one("SELECT * FROM customers")
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert result == ("Marvin", "Highway 42")

    def test_fetch_many_sync_context_returns_value_not_coroutine(self, tmp_path):
        """fetch_many must return list (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                result = connector.fetch_many("SELECT * FROM customers", size=2)
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_all_sync_context_returns_value_not_coroutine(self, tmp_path):
        """fetch_all must return list (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                result = connector.fetch_all("SELECT * FROM customers")
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_execute_sync_context_returns_value_not_coroutine(self, tmp_path):
        """execute must return CursorResult (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                result = connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert isinstance(result, CursorResult)

    def test_execute_many_sync_context_returns_value_not_coroutine(self, tmp_path):
        """execute_many must return CursorResult (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                result = connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert isinstance(result, CursorResult)

    def test_reset_connections_sync_context_returns_none_not_coroutine(self, tmp_path):
        """reset_connections must not return coroutine in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                connector.fetch_one("SELECT 1")
                result = connector.reset_connections()
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert result is None


class TestAsyncSqlAlchemyConnector:
    """Tests for AsyncSqlAlchemyConnector with async drivers."""

    async def test_fetch_one_async_context_works(self, tmp_path):
        """fetch_one should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                await connector.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
                result = await connector.fetch_one("SELECT * FROM customers")
                return result

        result = await test_flow()
        assert result == ("Marvin", "Highway 42")

    async def test_fetch_many_async_context_works(self, tmp_path):
        """fetch_many should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                await connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                result = await connector.fetch_many("SELECT * FROM customers", size=2)
                return result

        result = await test_flow()
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_fetch_all_async_context_works(self, tmp_path):
        """fetch_all should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                await connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                result = await connector.fetch_all("SELECT * FROM customers")
                return result

        result = await test_flow()
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_execute_async_context_works(self, tmp_path):
        """execute should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                result = await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                return result

        result = await test_flow()
        assert isinstance(result, CursorResult)

    async def test_execute_many_async_context_works(self, tmp_path):
        """execute_many should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                result = await connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                    ],
                )
                return result

        result = await test_flow()
        assert isinstance(result, CursorResult)

    async def test_reset_connections_async_context_works(self, tmp_path):
        """reset_connections should work correctly in async context."""

        @flow
        async def test_flow():
            async with AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                await connector.fetch_one("SELECT 1")
                result = await connector.reset_connections()
                return result

        result = await test_flow()
        assert result is None


class TestDriverTypeEnforcement:
    """Tests that verify sync connector rejects async drivers and vice versa."""

    def test_sync_connector_raises_for_async_driver(self, tmp_path):
        """SqlAlchemyConnector should raise ValueError when used with async drivers."""
        with pytest.raises(ValueError, match="async driver"):
            SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            )

    def test_async_connector_raises_for_sync_driver(self, tmp_path):
        """AsyncSqlAlchemyConnector should raise ValueError when used with sync drivers."""
        with pytest.raises(ValueError, match="sync driver"):
            AsyncSqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            )
