"""Tests for async_dispatch migration in prefect-gcp bigquery.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from typing import Coroutine
from unittest.mock import MagicMock

import pytest
from prefect_gcp.bigquery import (
    BigQueryWarehouse,
    abigquery_create_table,
    abigquery_insert_stream,
    abigquery_load_cloud_storage,
    abigquery_load_file,
    abigquery_query,
    bigquery_create_table,
    bigquery_insert_stream,
    bigquery_load_cloud_storage,
    bigquery_load_file,
    bigquery_query,
)

from prefect import flow


@pytest.fixture
def mock_connection():
    """Mock connection for BigQueryWarehouse tests."""
    mock_cursor = MagicMock()
    results = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    mock_cursor.fetchone.side_effect = lambda: (next(results),)
    mock_cursor.fetchmany.side_effect = lambda size: list(
        (next(results),) for i in range(size)
    )
    mock_cursor.fetchall.side_effect = lambda: [(result,) for result in results]

    mock_connection = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    return mock_connection


class TestBigQueryQueryAsyncDispatch:
    """Tests for bigquery_query migrated from @sync_compatible to @async_dispatch."""

    def test_bigquery_query_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """bigquery_query must return result (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            result = bigquery_query("SELECT 1", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_bigquery_query_async_context_works(self, gcp_credentials):
        """bigquery_query should work correctly in async context."""

        @flow
        async def test_flow():
            result = await abigquery_query("SELECT 1", gcp_credentials)
            return result

        result = await test_flow()
        assert result is not None

    def test_abigquery_query_is_available(self):
        """abigquery_query should be available for direct async usage."""
        assert callable(abigquery_query)


class TestBigQueryCreateTableAsyncDispatch:
    """Tests for bigquery_create_table migrated from @sync_compatible to @async_dispatch."""

    def test_bigquery_create_table_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """bigquery_create_table must return result (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = bigquery_create_table(
                "test_dataset",
                "test_table",
                gcp_credentials,
                schema=[{"name": "col1", "type": "STRING"}],
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_bigquery_create_table_async_context_works(self, gcp_credentials):
        """bigquery_create_table should work correctly in async context."""

        @flow
        async def test_flow():
            result = await abigquery_create_table(
                "test_dataset",
                "test_table",
                gcp_credentials,
                schema=[{"name": "col1", "type": "STRING"}],
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_abigquery_create_table_is_available(self):
        """abigquery_create_table should be available for direct async usage."""
        assert callable(abigquery_create_table)


class TestBigQueryInsertStreamAsyncDispatch:
    """Tests for bigquery_insert_stream migrated from @sync_compatible to @async_dispatch."""

    def test_bigquery_insert_stream_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """bigquery_insert_stream must return result (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = bigquery_insert_stream(
                "test_dataset",
                "test_table",
                [{"col1": "value1"}],
                gcp_credentials,
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_bigquery_insert_stream_async_context_works(self, gcp_credentials):
        """bigquery_insert_stream should work correctly in async context."""

        @flow
        async def test_flow():
            result = await abigquery_insert_stream(
                "test_dataset",
                "test_table",
                [{"col1": "value1"}],
                gcp_credentials,
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_abigquery_insert_stream_is_available(self):
        """abigquery_insert_stream should be available for direct async usage."""
        assert callable(abigquery_insert_stream)


class TestBigQueryLoadCloudStorageAsyncDispatch:
    """Tests for bigquery_load_cloud_storage migrated from @sync_compatible to @async_dispatch."""

    def test_bigquery_load_cloud_storage_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """bigquery_load_cloud_storage must return result (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = bigquery_load_cloud_storage(
                "test_dataset",
                "test_table",
                "gs://bucket/file.csv",
                gcp_credentials,
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_bigquery_load_cloud_storage_async_context_works(
        self, gcp_credentials
    ):
        """bigquery_load_cloud_storage should work correctly in async context."""

        @flow
        async def test_flow():
            result = await abigquery_load_cloud_storage(
                "test_dataset",
                "test_table",
                "gs://bucket/file.csv",
                gcp_credentials,
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_abigquery_load_cloud_storage_is_available(self):
        """abigquery_load_cloud_storage should be available for direct async usage."""
        assert callable(abigquery_load_cloud_storage)


class TestBigQueryLoadFileAsyncDispatch:
    """Tests for bigquery_load_file migrated from @sync_compatible to @async_dispatch."""

    def test_bigquery_load_file_sync_context_returns_value_not_coroutine(
        self, gcp_credentials, tmp_path
    ):
        """bigquery_load_file must return result (not coroutine) in sync context."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("col1\nvalue1")

        @flow
        def test_flow():
            result = bigquery_load_file(
                "test_dataset",
                "test_table",
                str(test_file),
                gcp_credentials,
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_bigquery_load_file_async_context_works(
        self, gcp_credentials, tmp_path
    ):
        """bigquery_load_file should work correctly in async context."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("col1\nvalue1")

        @flow
        async def test_flow():
            result = await abigquery_load_file(
                "test_dataset",
                "test_table",
                str(test_file),
                gcp_credentials,
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_abigquery_load_file_is_available(self):
        """abigquery_load_file should be available for direct async usage."""
        assert callable(abigquery_load_file)


class TestBigQueryWarehouseFetchOneAsyncDispatch:
    """Tests for BigQueryWarehouse.fetch_one migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def warehouse(self, gcp_credentials, mock_connection):
        warehouse = BigQueryWarehouse(gcp_credentials=gcp_credentials)
        warehouse._connection = mock_connection
        return warehouse

    def test_fetch_one_sync_context_returns_value_not_coroutine(self, warehouse):
        """fetch_one must return result (not coroutine) in sync context."""
        result = warehouse.fetch_one("SELECT 1")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_fetch_one_async_context_works(self, warehouse):
        """fetch_one should work correctly in async context."""
        result = await warehouse.afetch_one("SELECT 1")
        assert result is not None

    def test_afetch_one_is_available(self, warehouse):
        """afetch_one should be available for direct async usage."""
        assert hasattr(warehouse, "afetch_one")
        assert callable(warehouse.afetch_one)


class TestBigQueryWarehouseFetchManyAsyncDispatch:
    """Tests for BigQueryWarehouse.fetch_many migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def warehouse(self, gcp_credentials, mock_connection):
        warehouse = BigQueryWarehouse(gcp_credentials=gcp_credentials)
        warehouse._connection = mock_connection
        return warehouse

    def test_fetch_many_sync_context_returns_value_not_coroutine(self, warehouse):
        """fetch_many must return result (not coroutine) in sync context."""
        result = warehouse.fetch_many("SELECT 1", size=5)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_fetch_many_async_context_works(self, warehouse):
        """fetch_many should work correctly in async context."""
        result = await warehouse.afetch_many("SELECT 1", size=5)
        assert result is not None

    def test_afetch_many_is_available(self, warehouse):
        """afetch_many should be available for direct async usage."""
        assert hasattr(warehouse, "afetch_many")
        assert callable(warehouse.afetch_many)


class TestBigQueryWarehouseFetchAllAsyncDispatch:
    """Tests for BigQueryWarehouse.fetch_all migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def warehouse(self, gcp_credentials, mock_connection):
        warehouse = BigQueryWarehouse(gcp_credentials=gcp_credentials)
        warehouse._connection = mock_connection
        return warehouse

    def test_fetch_all_sync_context_returns_value_not_coroutine(self, warehouse):
        """fetch_all must return result (not coroutine) in sync context."""
        result = warehouse.fetch_all("SELECT 1")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_fetch_all_async_context_works(self, warehouse):
        """fetch_all should work correctly in async context."""
        result = await warehouse.afetch_all("SELECT 1")
        assert result is not None

    def test_afetch_all_is_available(self, warehouse):
        """afetch_all should be available for direct async usage."""
        assert hasattr(warehouse, "afetch_all")
        assert callable(warehouse.afetch_all)


class TestBigQueryWarehouseExecuteAsyncDispatch:
    """Tests for BigQueryWarehouse.execute migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def warehouse(self, gcp_credentials, mock_connection):
        warehouse = BigQueryWarehouse(gcp_credentials=gcp_credentials)
        warehouse._connection = mock_connection
        return warehouse

    def test_execute_sync_context_returns_value_not_coroutine(self, warehouse):
        """execute must return result (not coroutine) in sync context."""
        result = warehouse.execute("SELECT 1")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_execute_async_context_works(self, warehouse):
        """execute should work correctly in async context."""
        # execute returns None - just verify it doesn't raise
        await warehouse.aexecute("SELECT 1")

    def test_aexecute_is_available(self, warehouse):
        """aexecute should be available for direct async usage."""
        assert hasattr(warehouse, "aexecute")
        assert callable(warehouse.aexecute)


class TestBigQueryWarehouseExecuteManyAsyncDispatch:
    """Tests for BigQueryWarehouse.execute_many migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def warehouse(self, gcp_credentials, mock_connection):
        warehouse = BigQueryWarehouse(gcp_credentials=gcp_credentials)
        warehouse._connection = mock_connection
        return warehouse

    def test_execute_many_sync_context_returns_value_not_coroutine(self, warehouse):
        """execute_many must return result (not coroutine) in sync context."""
        result = warehouse.execute_many("SELECT 1", seq_of_parameters=[{}])
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_execute_many_async_context_works(self, warehouse):
        """execute_many should work correctly in async context."""
        # execute_many returns None - just verify it doesn't raise
        await warehouse.aexecute_many("SELECT 1", seq_of_parameters=[{}])

    def test_aexecute_many_is_available(self, warehouse):
        """aexecute_many should be available for direct async usage."""
        assert hasattr(warehouse, "aexecute_many")
        assert callable(warehouse.aexecute_many)
