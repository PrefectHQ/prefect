import inspect
from unittest.mock import MagicMock

import pytest
from prefect_snowflake.credentials import SnowflakeCredentials
from prefect_snowflake.database import (
    BEGIN_TRANSACTION_STATEMENT,
    END_TRANSACTION_STATEMENT,
    SnowflakeConnector,
    snowflake_multiquery,
    snowflake_multiquery_async,
    snowflake_query,
    snowflake_query_async,
)
from pydantic import SecretBytes, SecretStr
from snowflake.connector import DictCursor
from snowflake.connector.cursor import SnowflakeCursor as OriginalSnowflakeCursorClass

from prefect import flow


@pytest.fixture
def connector_params(credentials_params):
    snowflake_credentials = SnowflakeCredentials(**credentials_params)
    _connector_params = {
        "schema": "schema_input",
        "database": "database",
        "warehouse": "warehouse",
        "credentials": snowflake_credentials.model_dump(),
    }
    return _connector_params


@pytest.fixture
def private_connector_params(private_credentials_params):
    snowflake_credentials = SnowflakeCredentials(**private_credentials_params)
    _connector_params = {
        "schema": "schema_input",
        "database": "database",
        "warehouse": "warehouse",
        "credentials": snowflake_credentials.model_dump(),
    }
    return _connector_params


async def run_sync_or_async(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def test_snowflake_connector_init(connector_params):
    snowflake_connector = SnowflakeConnector(**connector_params)
    actual_connector_params = snowflake_connector.model_dump()
    for param in connector_params:
        expected = connector_params[param]
        if param == "schema":
            param = "schema_"
        actual = actual_connector_params[param]
        if isinstance(actual, (SecretStr, SecretBytes)):
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


@pytest.mark.parametrize("query_function", [snowflake_query, snowflake_query_async])
async def test_snowflake_query(query_function, snowflake_connector):
    @flow
    async def test_flow():
        result = await run_sync_or_async(
            query_function, "query", snowflake_connector, params=("param",)
        )
        return result

    result = await run_sync_or_async(test_flow)
    assert result[0][0] == "query"
    assert result[0][1] == ("param",)


@pytest.mark.parametrize(
    "query_function", [snowflake_multiquery, snowflake_multiquery_async]
)
async def test_snowflake_multiquery(query_function, snowflake_connector):
    @flow
    async def test_flow():
        result = await run_sync_or_async(
            query_function, ["query1", "query2"], snowflake_connector, params=("param",)
        )
        return result

    result = await run_sync_or_async(test_flow)
    assert result[0][0][0] == "query1"
    assert result[0][0][1] == ("param",)
    assert result[1][0][0] == "query2"
    assert result[1][0][1] == ("param",)


@pytest.mark.parametrize(
    "query_function", [snowflake_multiquery, snowflake_multiquery_async]
)
async def test_snowflake_multiquery_transaction(query_function, snowflake_connector):
    @flow
    async def test_flow():
        result = await run_sync_or_async(
            query_function,
            ["query1", "query2"],
            snowflake_connector,
            params=("param",),
            as_transaction=True,
        )
        return result

    result = await run_sync_or_async(test_flow)
    assert result[0][0][0] == "query1"
    assert result[0][0][1] == ("param",)
    assert result[1][0][0] == "query2"
    assert result[1][0][1] == ("param",)


@pytest.mark.parametrize(
    "query_function", [snowflake_multiquery, snowflake_multiquery_async]
)
async def test_snowflake_multiquery_transaction_with_transaction_control_results(
    query_function, snowflake_connector
):
    @flow
    async def test_flow():
        result = await run_sync_or_async(
            query_function,
            ["query1", "query2"],
            snowflake_connector,
            params=("param",),
            as_transaction=True,
            return_transaction_control_results=True,
        )
        return result

    result = await run_sync_or_async(test_flow)
    assert result[0][0][0] == BEGIN_TRANSACTION_STATEMENT
    assert result[1][0][0] == "query1"
    assert result[1][0][1] == ("param",)
    assert result[2][0][0] == "query2"
    assert result[2][0][1] == ("param",)
    assert result[3][0][0] == END_TRANSACTION_STATEMENT


def test_snowflake_private_connector_init(private_connector_params):
    snowflake_connector = SnowflakeConnector(**private_connector_params)
    actual_connector_params = snowflake_connector.model_dump()
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

    def test_block_initialization_handles_schema_alias(self, connector_params):
        # First, test the case where the schema is set with the alias
        connector_params["schema"] = "schema_input"
        connector_params.pop("schema_", None)
        connector = SnowflakeConnector(**connector_params)
        assert connector.schema_ == "schema_input"

        # Now, test the case where the schema is set with the field name
        connector_params["schema_"] = "schema_input"
        connector_params.pop("schema", None)
        connector = SnowflakeConnector(**connector_params)
        assert connector.schema_ == "schema_input"

    def test_block_initialization(self, snowflake_connector):
        assert snowflake_connector._connection is None
        assert snowflake_connector._unique_cursors is None

    def test_get_connection(self, snowflake_connector: SnowflakeConnector, caplog):
        connection = snowflake_connector.get_connection()
        assert snowflake_connector._connection is connection
        assert caplog.records[0].msg == "Started a new connection to Snowflake."

    def test_get_connection_multiple_calls(
        self, snowflake_connector: SnowflakeConnector, caplog
    ):
        connection1 = snowflake_connector.get_connection()
        connection2 = snowflake_connector.get_connection()

        assert connection1 is connection2
        assert caplog.records[0].msg == "Started a new connection to Snowflake."
        assert len(caplog.records) == 1

    def test_get_connection_context_manager_multiple_calls(
        self, snowflake_connector: SnowflakeConnector, caplog
    ):
        with snowflake_connector.get_connection():
            pass

        with snowflake_connector.get_connection():
            pass

        assert len(caplog.records) == 2
        assert caplog.records[0].msg == "Started a new connection to Snowflake."
        assert caplog.records[1].msg == "Started a new connection to Snowflake."

    def test_reset_cursors(self, snowflake_connector: SnowflakeConnector, caplog):
        mock_cursor = MagicMock()
        snowflake_connector.reset_cursors()
        assert caplog.records[0].msg == "There were no cursors to reset."

        snowflake_connector._start_connection()
        snowflake_connector._unique_cursors["12345"] = mock_cursor
        snowflake_connector.reset_cursors()
        assert len(snowflake_connector._unique_cursors) == 0
        mock_cursor.close.assert_called_once()

    @pytest.mark.parametrize("fetch_function_name", ["fetch_one", "fetch_one_async"])
    async def test_fetch_one(self, fetch_function_name, snowflake_connector):
        fetch_function = getattr(snowflake_connector, fetch_function_name)
        result = await run_sync_or_async(fetch_function, "SELECT 1", parameters=None)
        assert result == (0,)

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

    def test_fetch_all_executes_directly_on_cursor(
        self, snowflake_connector: SnowflakeConnector
    ):
        """Test that fetch_all executes directly on the cursor instead of using self.execute."""
        snowflake_connector._start_connection()
        mock_cursor = MagicMock()
        snowflake_connector._connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(1,)]

        result = snowflake_connector.fetch_all("SELECT 1")

        mock_cursor.execute.assert_called_once_with("SELECT 1", params=None)
        mock_cursor.fetchall.assert_called_once()
        assert result == [(1,)]

    def test_fetch_one_executes_directly_on_cursor(
        self, snowflake_connector: SnowflakeConnector
    ):
        """Test that fetch_one executes directly on the cursor instead of using self.execute."""
        snowflake_connector._start_connection()
        mock_cursor = MagicMock()
        snowflake_connector._connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        result = snowflake_connector.fetch_one("SELECT 1")

        mock_cursor.execute.assert_called_once_with("SELECT 1", params=None)
        mock_cursor.fetchone.assert_called_once()
        assert result == (1,)

    def test_fetch_many_executes_directly_on_cursor(
        self, snowflake_connector: SnowflakeConnector
    ):
        """Test that fetch_many executes directly on the cursor instead of using self.execute."""
        snowflake_connector._start_connection()
        mock_cursor = MagicMock()
        snowflake_connector._connection.cursor.return_value = mock_cursor
        mock_cursor.fetchmany.return_value = [(1,), (2,)]

        result = snowflake_connector.fetch_many("SELECT 1", size=2)

        mock_cursor.execute.assert_called_once_with("SELECT 1", params=None)
        mock_cursor.fetchmany.assert_called_once_with(size=2)
        assert result == [(1,), (2,)]

    @pytest.mark.parametrize("fetch_function_name", ["fetch_many", "fetch_many_async"])
    async def test_fetch_many(self, fetch_function_name, snowflake_connector):
        fetch_function = getattr(snowflake_connector, fetch_function_name)
        result = await run_sync_or_async(
            fetch_function, "SELECT 1", parameters=None, size=3
        )
        assert result == [(0,), (1,), (2,)]

    @pytest.mark.parametrize("fetch_function_name", ["fetch_all", "fetch_all_async"])
    async def test_fetch_all(self, fetch_function_name, snowflake_connector):
        fetch_function = getattr(snowflake_connector, fetch_function_name)
        result = await run_sync_or_async(fetch_function, "SELECT 1", parameters=None)
        assert result == [(0,), (1,), (2,), (3,), (4,)]

    def test_execute(self, snowflake_connector: SnowflakeConnector):
        assert snowflake_connector.execute("query", parameters=("param",)) is None

    @pytest.mark.parametrize(
        "execute_function_name", ["execute_many", "execute_many_async"]
    )
    async def test_execute_many(self, execute_function_name, snowflake_connector):
        execute_function = getattr(snowflake_connector, execute_function_name)
        await run_sync_or_async(
            execute_function,
            "INSERT INTO table VALUES (%(val)s)",
            seq_of_parameters=[{"val": 1}, {"val": 2}],
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

    async def test_fetch_one_async(self, snowflake_connector):
        async def fetch_one_async_wrapper():
            return await snowflake_connector.fetch_one_async(
                "SELECT 1", parameters=None
            )

        result = await fetch_one_async_wrapper()
        assert result == (0,)

    async def test_fetch_many_async(self, snowflake_connector):
        async def fetch_many_async_wrapper():
            return await snowflake_connector.fetch_many_async(
                "SELECT 1", parameters=None, size=3
            )

        result = await fetch_many_async_wrapper()
        assert result == [(0,), (1,), (2,)]

    async def test_fetch_all_async(self, snowflake_connector):
        async def fetch_all_async_wrapper():
            return await snowflake_connector.fetch_all_async(
                "SELECT 1", parameters=None
            )

        result = await fetch_all_async_wrapper()
        assert result == [(0,), (1,), (2,), (3,), (4,)]

    async def test_execute_many_async(self, snowflake_connector):
        async def execute_many_async_wrapper():
            await snowflake_connector.execute_many_async(
                "INSERT INTO table VALUES (%(val)s)",
                seq_of_parameters=[{"val": 1}, {"val": 2}],
            )

        await execute_many_async_wrapper()
