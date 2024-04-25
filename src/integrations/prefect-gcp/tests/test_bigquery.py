import os
from unittest.mock import MagicMock

import pytest
from google.cloud.bigquery import ExternalConfig, SchemaField
from google.cloud.bigquery.dbapi.connection import Connection
from prefect_gcp.bigquery import (
    BigQueryWarehouse,
    bigquery_create_table,
    bigquery_insert_stream,
    bigquery_load_cloud_storage,
    bigquery_load_file,
    bigquery_query,
)

from prefect import flow


@pytest.mark.parametrize("to_dataframe", [False, True])
@pytest.mark.parametrize("result_transformer", [None, lambda _: ("test_transformer",)])
@pytest.mark.parametrize("dry_run_max_bytes", [None, 5, 15])
def test_bigquery_query(
    to_dataframe, result_transformer, dry_run_max_bytes, gcp_credentials
):
    @flow
    def test_flow():
        return bigquery_query(
            "query",
            gcp_credentials,
            to_dataframe=to_dataframe,
            query_params=[("param", str, "parameter")],
            dry_run_max_bytes=dry_run_max_bytes,
            dataset="dataset",
            table="test_table",
            job_config={},
            project="project",
            location="US",
            result_transformer=result_transformer,
        )

    if dry_run_max_bytes is not None and dry_run_max_bytes < 10:
        with pytest.raises(RuntimeError):
            test_flow()
    else:
        result = test_flow()
        if to_dataframe:
            assert result == "dataframe_query"
        else:
            if result_transformer:
                assert result == ("test_transformer",)
            else:
                assert result == ["query"]


def test_bigquery_create_table(gcp_credentials):
    @flow
    def test_flow():
        schema = [
            SchemaField("number", field_type="INTEGER", mode="REQUIRED"),
            SchemaField("text", field_type="STRING", mode="REQUIRED"),
            SchemaField("bool", field_type="BOOLEAN"),
        ]
        table = bigquery_create_table(
            "dataset",
            "table",
            gcp_credentials,
            schema,
            clustering_fields=["text"],
        )
        return table

    assert test_flow() == "table"


@pytest.mark.parametrize(
    "external_config", [None, ExternalConfig(source_format="PARQUET")]
)
def test_bigquery_create_table_external(gcp_credentials, external_config):
    @flow
    def test_flow():
        table = bigquery_create_table(
            "dataset",
            "table",
            gcp_credentials,
            clustering_fields=["text"],
            external_config=external_config,
        )
        return table

    if external_config is None:
        with pytest.raises(ValueError, match="Either a schema or an external"):
            test_flow()
    else:
        assert test_flow() == "table"


def test_bigquery_insert_stream(gcp_credentials):
    records = [
        {"number": 1, "text": "abc", "bool": True},
        {"number": 2, "text": "def", "bool": False},
    ]

    @flow
    def test_flow():
        output = bigquery_insert_stream(
            "dataset",
            "table",
            records,
            gcp_credentials,
        )
        return output

    assert test_flow() == records


def test_bigquery_load_cloud_storage(gcp_credentials):
    @flow
    def test_flow():
        schema = [
            SchemaField("number", field_type="INTEGER", mode="REQUIRED"),
            SchemaField("text", field_type="STRING", mode="REQUIRED"),
            SchemaField("bool", field_type="BOOLEAN"),
        ]
        output = bigquery_load_cloud_storage(
            "dataset", "table", "uri", gcp_credentials, schema=schema
        )
        return output

    result = test_flow()
    assert result.output == "uri"
    assert result._client is None
    assert result._completion_lock is None


def test_bigquery_load_file(gcp_credentials):
    path = os.path.abspath(__file__)

    @flow
    def test_flow():
        schema = [
            SchemaField("number", field_type="INTEGER", mode="REQUIRED"),
            SchemaField("text", field_type="STRING", mode="REQUIRED"),
            SchemaField("bool", field_type="BOOLEAN"),
        ]
        output = bigquery_load_file(
            "dataset", "table", path, gcp_credentials, schema=schema
        )
        return output

    result = test_flow()
    assert result.output == "file"
    assert result._client is None
    assert result._completion_lock is None


class TestBigQueryWarehouse:
    @pytest.fixture
    def mock_connection(self):
        mock_cursor = MagicMock()
        results = iter([0, 1, 2, 3, 4])
        mock_cursor.fetchone.side_effect = lambda: (next(results),)
        mock_cursor.fetchmany.side_effect = lambda size: list(
            (next(results),) for i in range(size)
        )
        mock_cursor.fetchall.side_effect = lambda: [(result,) for result in results]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        return mock_connection

    @pytest.fixture
    def bigquery_warehouse(self, gcp_credentials):
        return BigQueryWarehouse(gcp_credentials=gcp_credentials, fetch_size=2)

    def test_init(self, bigquery_warehouse):
        assert isinstance(bigquery_warehouse._connection, Connection)
        assert isinstance(bigquery_warehouse._unique_cursors, dict)
        assert bigquery_warehouse.fetch_size == 2

    def test_close(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        assert bigquery_warehouse._connection is not None
        bigquery_warehouse.close()
        assert bigquery_warehouse._unique_cursors == {}
        mock_connection.close.assert_called_once()
        assert bigquery_warehouse._connection is None

    def test_context_management(self, gcp_credentials):
        with BigQueryWarehouse(
            gcp_credentials=gcp_credentials, fetch_size=2
        ) as warehouse:
            assert isinstance(warehouse._connection, Connection)
            assert isinstance(warehouse._unique_cursors, dict)
            assert warehouse.fetch_size == 2
        assert warehouse._connection is None
        assert warehouse._unique_cursors == {}

    def test_get_connection(self, bigquery_warehouse):
        assert bigquery_warehouse.get_connection() == bigquery_warehouse._connection
        bigquery_warehouse.close()
        assert bigquery_warehouse.get_connection() is None

    def test_cursor_lifecycle(self, bigquery_warehouse, mock_connection):
        # check if uses the same cursor
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "b"})
        assert result == (0,)

        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "b"})
        assert result == (1,)

        # cursor only created once
        assert bigquery_warehouse._connection.cursor.call_count == 1
        assert len(bigquery_warehouse._unique_cursors) == 1

        # until inputs change, then new cursor is created
        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "c"})
        assert bigquery_warehouse._connection.cursor.call_count == 2
        assert len(bigquery_warehouse._unique_cursors) == 2

        # check resetting
        cursors = bigquery_warehouse._unique_cursors
        bigquery_warehouse.reset_cursors()
        for cursor in cursors:
            assert cursor.close.call_count == 1
        assert bigquery_warehouse._unique_cursors == {}

    def test_fetch_one(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "b"})
        assert result == (0,)

        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "b"})
        assert result == (1,)

    def test_fetch_many(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.fetch_many("operation", parameters={"a": "b"})
        assert result == [(0,), (1,)]

        result = bigquery_warehouse.fetch_many(
            "operation", parameters={"a": "b"}, size=3
        )
        assert result == [(2,), (3,), (4,)]

    def test_fetch_all(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.fetch_all("operation", parameters={"a": "b"})
        assert result == [(0,), (1,), (2,), (3,), (4,)]

        result = bigquery_warehouse.fetch_all("operation", parameters={"a": "b"})
        assert result == []

    def test_fetch_methods(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.fetch_one("operation", parameters={"a": "b"})
        assert result == (0,)

        result = bigquery_warehouse.fetch_many("operation", parameters={"a": "b"})
        assert result == [(1,), (2,)]

        result = bigquery_warehouse.fetch_all("operation", parameters={"a": "b"})
        assert result == [(3,), (4,)]

    def test_execute(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.execute("operation", parameters={"a": "b"})
        assert result is None
        assert mock_connection.cursor().execute.call_once_with(
            "operation", parameters={"a": "b"}
        )

    def test_execute_many(self, bigquery_warehouse, mock_connection):
        bigquery_warehouse._connection = mock_connection
        result = bigquery_warehouse.execute_many(
            "operation", seq_of_parameters=[{"a": "b"}, {"c", "d"}]
        )
        assert result is None
        assert mock_connection.cursor().executemany.call_once_with(
            "operation", seq_of_parameters=[{"a": "b"}, {"c", "d"}]
        )
