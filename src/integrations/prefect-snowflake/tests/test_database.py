from unittest.mock import MagicMock

import pytest
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import flow

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import SecretBytes, SecretStr
else:
    from pydantic import SecretBytes, SecretStr

from prefect_snowflake.database import (
    BEGIN_TRANSACTION_STATEMENT,
    END_TRANSACTION_STATEMENT,
    SnowflakeConnector,
    snowflake_multiquery,
    snowflake_query,
    snowflake_query_sync,
)
from snowflake.connector import DictCursor
from snowflake.connector.cursor import SnowflakeCursor as OriginalSnowflakeCursorClass


def test_snowflake_connector_init(connector_params):
    snowflake_connector = SnowflakeConnector(**connector_params)
    actual_connector_params = snowflake_connector.dict()
    for param in connector_params:
        expected = connector_params[param]
        if param == "schema":
            param = "schema_"
        actual = actual_connector_params[param]
        if isinstance(actual, SecretStr):
            actual = actual.get_secret_value()
        assert actual == expected


def test_snowflake_connector_password_is_secret_str(connector_params):
    snowflake_connector = SnowflakeConnector(**connector_params)
    password = snowflake_connector.credentials.password
    assert isinstance(password, SecretStr)
    assert password.get_secret_value() == "password"


def test_snowflake_connector_private_key_is_secret(private_connector_params):
    snowflake_connector = SnowflakeConnector(**private_connector_params)
    private_key = snowflake_connector.credentials.private_key
    assert isinstance(private_key, (SecretStr, SecretBytes))


class SnowflakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute_async(self, query, params):
        query_id = "1234"
        self.result = {query_id: [(query, params)]}
        return {"queryId": query_id}

    def get_results_from_sfqid(self, query_id):
        self.query_result = self.result[query_id]

    def fetchall(self):
        return self.query_result

    def execute(self, query, params=None):
        self.query_result = [(query, params, "sync")]
        return self


class SnowflakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, cursor_type):
        return SnowflakeCursor()

    def is_still_running(self, state):
        return state

    def get_query_status_throw_if_error(self, query_id):
        return False


@pytest.fixture()
def snowflake_connector(snowflake_connect_mock):
    snowflake_connector_mock = MagicMock()
    snowflake_connector_mock.get_connection.return_value = SnowflakeConnection()
    return snowflake_connector_mock


def test_snowflake_query(snowflake_connector):
    @flow
    def test_flow():
        result = snowflake_query(
            "query",
            snowflake_connector,
            params=("param",),
        )
        return result

    result = test_flow()
    assert result[0][0] == "query"
    assert result[0][1] == ("param",)


def test_snowflake_multiquery(snowflake_connector):
    @flow
    def test_flow():
        result = snowflake_multiquery(
            ["query1", "query2"],
            snowflake_connector,
            params=("param",),
        )
        return result

    result = test_flow()
    assert result[0][0][0] == "query1"
    assert result[0][0][1] == ("param",)
    assert result[1][0][0] == "query2"
    assert result[1][0][1] == ("param",)


def test_snowflake_multiquery_transaction(snowflake_connector):
    @flow
    def test_flow():
        result = snowflake_multiquery(
            ["query1", "query2"],
            snowflake_connector,
            params=("param",),
            as_transaction=True,
        )
        return result

    result = test_flow()
    assert result[0][0][0] == "query1"
    assert result[0][0][1] == ("param",)
    assert result[1][0][0] == "query2"
    assert result[1][0][1] == ("param",)


def test_snowflake_multiquery_transaction_with_transaction_control_results(
    snowflake_connector,
):
    @flow
    def test_flow():
        result = snowflake_multiquery(
            ["query1", "query2"],
            snowflake_connector,
            params=("param",),
            as_transaction=True,
            return_transaction_control_results=True,
        )
        return result

    result = test_flow()
    assert result[0][0][0] == BEGIN_TRANSACTION_STATEMENT
    assert result[1][0][0] == "query1"
    assert result[1][0][1] == ("param",)
    assert result[2][0][0] == "query2"
    assert result[2][0][1] == ("param",)
    assert result[3][0][0] == END_TRANSACTION_STATEMENT


def test_snowflake_query_sync(snowflake_connector):
    @flow()
    def test_snowflake_query_sync_flow():
        result = snowflake_query_sync("query", snowflake_connector, params=("param",))
        return result

    result = test_snowflake_query_sync_flow()
    assert result[0][0] == "query"
    assert result[0][1] == ("param",)
    assert result[0][2] == "sync"


def test_snowflake_private_connector_init(private_connector_params):
    snowflake_connector = SnowflakeConnector(**private_connector_params)
    actual_connector_params = snowflake_connector.dict()
    for param in private_connector_params:
        expected = private_connector_params[param]
        if param == "schema":
            param = "schema_"
        actual = actual_connector_params[param]
        if isinstance(actual, (SecretStr, SecretBytes)):
            actual = actual.get_secret_value()
        assert actual == expected


class TestSnowflakeConnector:
    @pytest.fixture
    def snowflake_connector(self, connector_params, snowflake_connect_mock):
        connector = SnowflakeConnector(**connector_params)
        return connector

    def test_block_initialization(self, snowflake_connector):
        assert snowflake_connector._connection is None
        assert snowflake_connector._unique_cursors is None

    def test_get_connection(self, snowflake_connector: SnowflakeConnector, caplog):
        connection = snowflake_connector.get_connection()
        assert snowflake_connector._connection is connection
        assert caplog.records[0].msg == "Started a new connection to Snowflake."

    def test_reset_cursors(self, snowflake_connector: SnowflakeConnector, caplog):
        mock_cursor = MagicMock()
        snowflake_connector.reset_cursors()
        assert caplog.records[0].msg == "There were no cursors to reset."

        snowflake_connector._start_connection()
        snowflake_connector._unique_cursors["12345"] = mock_cursor
        snowflake_connector.reset_cursors()
        assert len(snowflake_connector._unique_cursors) == 0
        mock_cursor.close.assert_called_once()

    def test_fetch_one(self, snowflake_connector: SnowflakeConnector):
        result = snowflake_connector.fetch_one("query", parameters=("param",))
        assert result == (0,)
        result = snowflake_connector.fetch_one("query", parameters=("param",))
        assert result == (1,)

    def test_fetch_one_cursor_set_to_dict_cursor(
        self, snowflake_connector: SnowflakeConnector
    ):
        _ = snowflake_connector.fetch_one(
            "query", parameters=("param",), cursor_type=DictCursor
        )
        args, _ = snowflake_connector._connection.cursor.call_args

        assert args[0] == DictCursor

    def test_fetch_one_cursor_default(self, snowflake_connector: SnowflakeConnector):
        _ = snowflake_connector.fetch_one("query", parameters=("param",))
        args, kwargs = snowflake_connector._connection.cursor.call_args

        assert args[0] == OriginalSnowflakeCursorClass

    def test_fetch_all_cursor_set_to_dict_cursor(
        self, snowflake_connector: SnowflakeConnector
    ):
        _ = snowflake_connector.fetch_all(
            "query", parameters=("param",), cursor_type=DictCursor
        )
        args, _ = snowflake_connector._connection.cursor.call_args

        assert args[0] == DictCursor

    def test_fetch_all_cursor_default(self, snowflake_connector: SnowflakeConnector):
        _ = snowflake_connector.fetch_all("query", parameters=("param",))
        args, _ = snowflake_connector._connection.cursor.call_args

        assert args[0] == OriginalSnowflakeCursorClass

    def test_fetch_many(self, snowflake_connector: SnowflakeConnector):
        result = snowflake_connector.fetch_many("query", parameters=("param",), size=2)
        assert result == [(0,), (1,)]
        result = snowflake_connector.fetch_many("query", parameters=("param",))
        assert result == [(2,)]

    def test_fetch_all(self, snowflake_connector: SnowflakeConnector):
        result = snowflake_connector.fetch_all("query", parameters=("param",))
        assert result == [(0,), (1,), (2,), (3,), (4,)]

    def test_execute(self, snowflake_connector: SnowflakeConnector):
        assert snowflake_connector.execute("query", parameters=("param",)) is None

    def test_execute_Many(self, snowflake_connector: SnowflakeConnector):
        assert (
            snowflake_connector.execute_many("query", seq_of_parameters=[("param",)])
            is None
        )

    def test_close(self, snowflake_connector: SnowflakeConnector, caplog):
        assert snowflake_connector.close() is None
        assert caplog.records[0].msg == "There were no cursors to reset."
        assert caplog.records[1].msg == "There was no connection open to be closed."

        snowflake_connector._start_connection()
        assert snowflake_connector.close() is None
        assert snowflake_connector._connection is None
        assert snowflake_connector._unique_cursors == {}

    def test_context_management(self, snowflake_connector):
        with snowflake_connector:
            assert snowflake_connector._connection is None
            assert snowflake_connector._unique_cursors is None

        assert snowflake_connector._connection is None
        assert snowflake_connector._unique_cursors is None
