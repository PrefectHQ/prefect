"""Tests for async_dispatch migration in prefect-sqlalchemy.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from typing import Coroutine

import pytest
from prefect_sqlalchemy.credentials import (
    AsyncDriver,
    ConnectionComponents,
    SyncDriver,
)
from prefect_sqlalchemy.database import SqlAlchemyConnector

from prefect import flow


class TestSqlAlchemyConnectorAsyncDispatch:
    """Tests for SqlAlchemyConnector methods migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def sync_connector(self, tmp_path):
        """Create a sync SQLite connector with test data."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            ),
            fetch_size=2,
        )
        with connector:
            connector.execute(
                "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
            )
            connector.execute(
                "INSERT INTO customers (name, address) VALUES (:name, :address);",
                parameters={"name": "Marvin", "address": "Highway 42"},
            )
            yield connector

    @pytest.fixture
    async def async_connector(self, tmp_path):
        """Create an async SQLite connector with test data."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=AsyncDriver.SQLITE_AIOSQLITE,
                database=str(tmp_path / "test.db"),
            ),
            fetch_size=2,
        )
        async with connector:
            await connector.aexecute(
                "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
            )
            await connector.aexecute(
                "INSERT INTO customers (name, address) VALUES (:name, :address);",
                parameters={"name": "Marvin", "address": "Highway 42"},
            )
            yield connector


class TestFetchOneAsyncDispatch:
    """Tests for fetch_one migrated from @sync_compatible to @async_dispatch."""

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

    async def test_afetch_one_async_context_works(self, tmp_path):
        """afetch_one should work correctly in async context."""

        @flow
        async def test_flow():
            async with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=AsyncDriver.SQLITE_AIOSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as connector:
                await connector.aexecute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
                )
                await connector.aexecute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
                result = await connector.afetch_one("SELECT * FROM customers")
                return result

        result = await test_flow()
        assert result == ("Marvin", "Highway 42")

    def test_afetch_one_is_available(self, tmp_path):
        """afetch_one should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "afetch_one")
        assert callable(connector.afetch_one)


class TestFetchManyAsyncDispatch:
    """Tests for fetch_many migrated from @sync_compatible to @async_dispatch."""

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

    def test_afetch_many_is_available(self, tmp_path):
        """afetch_many should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "afetch_many")
        assert callable(connector.afetch_many)


class TestFetchAllAsyncDispatch:
    """Tests for fetch_all migrated from @sync_compatible to @async_dispatch."""

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

    def test_afetch_all_is_available(self, tmp_path):
        """afetch_all should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "afetch_all")
        assert callable(connector.afetch_all)


class TestExecuteAsyncDispatch:
    """Tests for execute migrated from @sync_compatible to @async_dispatch."""

    def test_execute_sync_context_returns_value_not_coroutine(self, tmp_path):
        """execute must return CursorResult (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        from sqlalchemy.engine.cursor import CursorResult

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

    def test_aexecute_is_available(self, tmp_path):
        """aexecute should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "aexecute")
        assert callable(connector.aexecute)


class TestExecuteManyAsyncDispatch:
    """Tests for execute_many migrated from @sync_compatible to @async_dispatch."""

    def test_execute_many_sync_context_returns_value_not_coroutine(self, tmp_path):
        """execute_many must return CursorResult (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        from sqlalchemy.engine.cursor import CursorResult

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

    def test_aexecute_many_is_available(self, tmp_path):
        """aexecute_many should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "aexecute_many")
        assert callable(connector.aexecute_many)


class TestResetConnectionsAsyncDispatch:
    """Tests for reset_connections migrated from @sync_compatible to @async_dispatch."""

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

    def test_reset_async_connections_is_available(self, tmp_path):
        """reset_async_connections should be available for direct async usage."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        assert hasattr(connector, "reset_async_connections")
        assert callable(connector.reset_async_connections)


class TestDriverTypeEnforcement:
    """Tests that verify sync methods raise errors for async drivers and vice versa."""

    def test_sync_method_raises_for_async_driver(self, tmp_path):
        """Sync methods should raise RuntimeError when used with async drivers."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=AsyncDriver.SQLITE_AIOSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        with pytest.raises(RuntimeError, match="is an async driver"):
            connector.fetch_one("SELECT 1")

    async def test_async_method_raises_for_sync_driver(self, tmp_path):
        """Async methods should raise RuntimeError when used with sync drivers."""
        connector = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        with pytest.raises(RuntimeError, match="is not an async driver"):
            await connector.afetch_one("SELECT 1")
