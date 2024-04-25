from contextlib import ExitStack, asynccontextmanager, contextmanager
from unittest.mock import MagicMock

import cloudpickle
import pytest
from prefect_sqlalchemy.credentials import (
    AsyncDriver,
    ConnectionComponents,
    DatabaseCredentials,
    SyncDriver,
)
from prefect_sqlalchemy.database import (
    SqlAlchemyConnector,
    sqlalchemy_execute,
    sqlalchemy_query,
)
from sqlalchemy import __version__ as SQLALCHEMY_VERSION
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from prefect import flow, task


class SQLAlchemyAsyncEngineMock:
    async def dispose(self):
        return True

    @asynccontextmanager
    async def connect(self):
        try:
            yield SQLAlchemyAsyncConnectionMock()
        finally:
            pass


class SQLAlchemyAsyncConnectionMock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, query, params):
        cursor_result = MagicMock()
        cursor_result.fetchall.side_effect = lambda: [
            (query, params),
        ]
        cursor_result.fetchmany.side_effect = (
            lambda size: [
                (query, params),
            ]
            * size
        )
        return cursor_result

    async def commit(self):
        pass


class SQLAlchemyEngineMock:
    def dispose(self):
        return True

    @contextmanager
    def connect(self):
        try:
            yield SQLAlchemyConnectionMock()
        finally:
            pass


class SQLAlchemyConnectionMock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params):
        cursor_result = MagicMock()
        cursor_result.fetchall.side_effect = lambda: [
            (query, params),
        ]
        cursor_result.fetchmany.side_effect = (
            lambda size: [
                (query, params),
            ]
            * size
        )
        return cursor_result

    def commit(self):
        pass


@pytest.fixture()
def sqlalchemy_credentials_async():
    sqlalchemy_credentials_mock = MagicMock()
    sqlalchemy_credentials_mock._driver_is_async = True
    sqlalchemy_credentials_mock.get_engine.return_value = SQLAlchemyAsyncEngineMock()
    return sqlalchemy_credentials_mock


@pytest.fixture()
def sqlalchemy_credentials_sync():
    sqlalchemy_credentials_mock = MagicMock()
    sqlalchemy_credentials_mock._driver_is_async = False
    sqlalchemy_credentials_mock.get_engine.return_value = SQLAlchemyEngineMock()
    return sqlalchemy_credentials_mock


@pytest.mark.parametrize("limit", [None, 3])
async def test_sqlalchemy_query_async(limit, sqlalchemy_credentials_async):
    @flow
    async def test_flow():
        result = await sqlalchemy_query(
            "query", sqlalchemy_credentials_async, params=("param",), limit=limit
        )
        return result

    result = await test_flow()
    assert str(result[0][0]) == "query"
    assert result[0][1] == ("param",)
    if limit is None:
        assert len(result) == 1
    else:
        assert len(result) == limit


@pytest.mark.parametrize("limit", [None, 3])
def test_sqlalchemy_query_sync(limit, sqlalchemy_credentials_sync):
    @flow
    def test_flow():
        result = sqlalchemy_query(
            "query", sqlalchemy_credentials_sync, params=("param",), limit=limit
        )
        return result

    result = test_flow()
    assert str(result[0][0]) == "query"
    assert result[0][1] == ("param",)
    if limit is None:
        assert len(result) == 1
    else:
        assert len(result) == limit


async def test_sqlalchemy_execute_async(sqlalchemy_credentials_async):
    @flow
    async def test_flow():
        result = await sqlalchemy_execute.submit(
            "statement", sqlalchemy_credentials_async
        )
        return result

    result = await test_flow()
    assert await result.result() is None


def test_sqlalchemy_execute_sync(sqlalchemy_credentials_sync):
    @flow
    def test_flow():
        result = sqlalchemy_execute.submit("statement", sqlalchemy_credentials_sync)
        return result

    result = test_flow()
    assert result.result() is None


def test_sqlalchemy_execute_twice_no_error(sqlalchemy_credentials_sync):
    @flow
    def test_flow():
        result = sqlalchemy_execute.submit("statement", sqlalchemy_credentials_sync)
        result = sqlalchemy_execute.submit("statement", sqlalchemy_credentials_sync)
        return result

    result = test_flow()
    assert result.result() is None


def test_sqlalchemy_execute_sqlite(tmp_path):
    @flow
    def sqlalchemy_execute_flow():
        sqlalchemy_credentials = DatabaseCredentials(
            driver=SyncDriver.SQLITE_PYSQLITE,
            database=str(tmp_path / "prefect.db"),
        )
        sqlalchemy_execute(
            "CREATE TABLE customers (name varchar, address varchar);",
            sqlalchemy_credentials,
        )
        sqlalchemy_execute(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            sqlalchemy_credentials,
            params={"name": "Marvin", "address": "Highway 42"},
        )
        result = sqlalchemy_query(
            "SELECT * FROM customers WHERE name = :name;",
            sqlalchemy_credentials,
            params={"name": "Marvin"},
        )
        return result

    rows = sqlalchemy_execute_flow()
    assert len(rows) == 1

    row = rows[0]
    assert len(row) == 2
    assert row[0] == "Marvin"
    assert row[1] == "Highway 42"


async def test_sqlalchemy_execute_sqlite_async(tmp_path):
    @flow
    async def sqlalchemy_execute_flow():
        sqlalchemy_credentials = DatabaseCredentials(
            driver=AsyncDriver.SQLITE_AIOSQLITE,
            database=str(tmp_path / "prefect_async.db"),
        )
        await sqlalchemy_execute(
            "CREATE TABLE customers (name varchar, address varchar);",
            sqlalchemy_credentials,
        )
        await sqlalchemy_execute(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            sqlalchemy_credentials,
            params={"name": "Marvin", "address": "Highway 42"},
        )
        await sqlalchemy_execute(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            sqlalchemy_credentials,
            params={"name": "Ford", "address": "Highway 42"},
        )
        result = await sqlalchemy_query(
            "SELECT * FROM customers WHERE address = :address;",
            sqlalchemy_credentials,
            params={"address": "Highway 42"},
        )
        return result

    rows = await sqlalchemy_execute_flow()
    assert len(rows) == 2

    expected_names = {"Ford", "Marvin"}
    expected_address = "Highway 42"
    actual_names, actual_addresses = zip(*rows)
    assert expected_names == set(actual_names)
    assert expected_address == actual_addresses[0]


class TestSqlAlchemyConnector:
    async def test_connector_init(self):
        credentials_components = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.POSTGRESQL_PSYCOPG2,
                username="myusername",
                password="mypass",
                database="my.db",
                host="localhost",
                port=1234,
            ),
        )

        connection_url = "postgresql+psycopg2://myusername:mypass@localhost:1234/my.db"
        credentials_url = SqlAlchemyConnector(connection_info=connection_url)
        assert credentials_components._rendered_url == credentials_url._rendered_url

    @pytest.mark.parametrize("method", ["fetch_all", "execute"])
    def test_delay_start(self, caplog, method):
        with SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=":memory:",
            ),
        ) as connector:
            assert connector._unique_results == {}
            assert isinstance(connector._exit_stack, ExitStack)
            connector.reset_connections()
            assert (
                caplog.records[0].msg == "Reset opened connections and their results."
            )
            assert connector._engine is None
            assert connector._unique_results == {}
            assert isinstance(connector._exit_stack, ExitStack)
            getattr(connector, method)("SELECT 1")
            assert isinstance(connector._engine, Engine)
            if method == "execute":
                assert connector._unique_results == {}
            else:
                assert len(connector._unique_results) == 1
            assert isinstance(connector._exit_stack, ExitStack)

    @pytest.fixture(params=[SyncDriver.SQLITE_PYSQLITE, AsyncDriver.SQLITE_AIOSQLITE])
    async def connector_with_data(self, tmp_path, request):
        credentials = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=request.param,
                database=str(tmp_path / "test.db"),
            ),
            fetch_size=2,
        )
        await credentials.execute(
            "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
        )
        await credentials.execute(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            parameters={"name": "Marvin", "address": "Highway 42"},
        )
        await credentials.execute_many(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            seq_of_parameters=[
                {"name": "Ford", "address": "Highway 42"},
                {"name": "Unknown", "address": "Space"},
                {"name": "Me", "address": "Myway 88"},
            ],
        )
        yield credentials

    @pytest.fixture(params=[True, False])
    async def managed_connector_with_data(self, connector_with_data, request):
        if request.param:
            # managed
            if connector_with_data._driver_is_async:
                async with connector_with_data:
                    yield connector_with_data
            else:
                with connector_with_data:
                    yield connector_with_data
                # need to reset manually because
                # the function is sync_compatible, but the test is an async function
                # so calling the close method in this async context results in:
                # 'SqlAlchemyConnector.reset_connections' was never awaited
                # but normally it's run in a sync function, which properly closes
                connector_with_data._reset_cursor_results()
        else:
            yield connector_with_data
            if connector_with_data._driver_is_async:
                await connector_with_data.aclose()
            else:
                connector_with_data._reset_cursor_results()
                connector_with_data._exit_stack.close()
                connector_with_data._engine = None
        assert connector_with_data._unique_results == {}
        assert connector_with_data._engine is None

    @pytest.mark.parametrize("begin", [True, False])
    async def test_get_connection(self, begin, managed_connector_with_data):
        connection = managed_connector_with_data.get_connection(begin=begin)
        if begin:
            engine_type = (
                AsyncEngine if managed_connector_with_data._driver_is_async else Engine
            )

            if SQLALCHEMY_VERSION.startswith("1."):
                assert isinstance(connection, engine_type._trans_ctx)
            elif managed_connector_with_data._driver_is_async:
                async with connection as conn:
                    assert isinstance(conn, engine_type._connection_cls)
            else:
                with connection as conn:
                    assert isinstance(conn, engine_type._connection_cls)
        else:
            engine_type = (
                AsyncConnection
                if managed_connector_with_data._driver_is_async
                else Connection
            )
            assert isinstance(connection, engine_type)

    @pytest.mark.parametrize("begin", [True, False])
    async def test_get_client(self, begin, managed_connector_with_data):
        connection = managed_connector_with_data.get_client(
            client_type="connection", begin=begin
        )
        if begin:
            engine_type = (
                AsyncEngine if managed_connector_with_data._driver_is_async else Engine
            )
            if SQLALCHEMY_VERSION.startswith("1."):
                assert isinstance(connection, engine_type._trans_ctx)
            elif managed_connector_with_data._driver_is_async:
                async with connection as conn:
                    assert isinstance(conn, engine_type._connection_cls)
            else:
                with connection as conn:
                    assert isinstance(conn, engine_type._connection_cls)
        else:
            engine_type = (
                AsyncConnection
                if managed_connector_with_data._driver_is_async
                else Connection
            )
            assert isinstance(connection, engine_type)

    async def test_reset_connections_sync_async_error(
        self, managed_connector_with_data
    ):
        with pytest.raises(RuntimeError, match="synchronous connections"):
            if managed_connector_with_data._driver_is_async:
                await managed_connector_with_data.reset_connections()
            else:
                await managed_connector_with_data.reset_async_connections()

    async def test_fetch_one(self, managed_connector_with_data):
        results = await managed_connector_with_data.fetch_one("SELECT * FROM customers")
        assert results == ("Marvin", "Highway 42")
        results = await managed_connector_with_data.fetch_one("SELECT * FROM customers")
        assert results == ("Ford", "Highway 42")

        # test with parameters
        results = await managed_connector_with_data.fetch_one(
            "SELECT * FROM customers WHERE address = :address",
            parameters={"address": "Myway 88"},
        )
        assert results == ("Me", "Myway 88")
        assert len(managed_connector_with_data._unique_results) == 2

        # now reset so fetch starts at the first value again
        if managed_connector_with_data._driver_is_async:
            await managed_connector_with_data.reset_async_connections()
        else:
            await managed_connector_with_data.reset_connections()
        assert len(managed_connector_with_data._unique_results) == 0

        # ensure it's really reset
        results = await managed_connector_with_data.fetch_one("SELECT * FROM customers")
        assert results == ("Marvin", "Highway 42")
        assert len(managed_connector_with_data._unique_results) == 1

    @pytest.mark.parametrize("size", [None, 1, 2])
    async def test_fetch_many(self, managed_connector_with_data, size):
        results = await managed_connector_with_data.fetch_many(
            "SELECT * FROM customers", size=size
        )
        expected = [("Marvin", "Highway 42"), ("Ford", "Highway 42")][
            : (size or managed_connector_with_data.fetch_size)
        ]
        assert results == expected

        # test with parameters
        results = await managed_connector_with_data.fetch_many(
            "SELECT * FROM customers WHERE address = :address",
            parameters={"address": "Myway 88"},
        )
        assert results == [("Me", "Myway 88")]
        assert len(managed_connector_with_data._unique_results) == 2

        # now reset so fetch starts at the first value again
        if managed_connector_with_data._driver_is_async:
            await managed_connector_with_data.reset_async_connections()
        else:
            await managed_connector_with_data.reset_connections()
        assert len(managed_connector_with_data._unique_results) == 0

        # ensure it's really reset
        results = await managed_connector_with_data.fetch_many(
            "SELECT * FROM customers", size=3
        )
        assert results == [
            ("Marvin", "Highway 42"),
            ("Ford", "Highway 42"),
            ("Unknown", "Space"),
        ]
        assert len(managed_connector_with_data._unique_results) == 1

    async def test_fetch_all(self, managed_connector_with_data):
        # test with parameters
        results = await managed_connector_with_data.fetch_all(
            "SELECT * FROM customers WHERE address = :address",
            parameters={"address": "Highway 42"},
        )
        expected = [("Marvin", "Highway 42"), ("Ford", "Highway 42")]
        assert results == expected

        # there should be no more results
        results = await managed_connector_with_data.fetch_all(
            "SELECT * FROM customers WHERE address = :address",
            parameters={"address": "Highway 42"},
        )
        assert results == []
        assert len(managed_connector_with_data._unique_results) == 1

        # now reset so fetch one starts at the first value again
        if managed_connector_with_data._driver_is_async:
            await managed_connector_with_data.reset_async_connections()
        else:
            await managed_connector_with_data.reset_connections()
        assert len(managed_connector_with_data._unique_results) == 0

        # ensure it's really reset
        results = await managed_connector_with_data.fetch_all(
            "SELECT * FROM customers WHERE address = :address",
            parameters={"address": "Highway 42"},
        )
        expected = [("Marvin", "Highway 42"), ("Ford", "Highway 42")]
        assert results == expected
        assert len(managed_connector_with_data._unique_results) == 1

    async def test_pickleable(self, managed_connector_with_data):
        await managed_connector_with_data.fetch_one("SELECT * FROM customers")
        pkl = cloudpickle.dumps(managed_connector_with_data)
        assert pkl
        assert cloudpickle.loads(pkl)

    def test_close(self, managed_connector_with_data):
        if managed_connector_with_data._driver_is_async:
            with pytest.raises(RuntimeError, match="Please use the"):
                managed_connector_with_data.close()
        else:
            managed_connector_with_data.close()  # test calling it twice

    async def test_aclose(self, managed_connector_with_data):
        if not managed_connector_with_data._driver_is_async:
            with pytest.raises(RuntimeError, match="Please use the"):
                await managed_connector_with_data.aclose()
        else:
            await managed_connector_with_data.aclose()  # test calling it twice

    async def test_enter(self, managed_connector_with_data):
        if managed_connector_with_data._driver_is_async:
            with pytest.raises(RuntimeError, match="cannot be run"):
                with managed_connector_with_data:
                    pass

    async def test_aenter(self, managed_connector_with_data):
        if not managed_connector_with_data._driver_is_async:
            with pytest.raises(RuntimeError, match="cannot be run"):
                async with managed_connector_with_data:
                    pass

    def test_sync_sqlite_in_flow(self, tmp_path):
        @flow
        def a_flow():
            with SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"  # noqa
                )
                conn.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
                conn.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                        {"name": "Me", "address": "Myway 88"},
                    ],
                )
                return conn.fetch_one("SELECT * FROM customers")

        assert a_flow() == ("Marvin", "Highway 42")

    def test_sync_compatible_reset_connections(self, tmp_path):
        conn = SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database=str(tmp_path / "test.db"),
            )
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"  # noqa
        )
        conn.execute(
            "INSERT INTO customers (name, address) VALUES (:name, :address);",
            parameters={"name": "Marvin", "address": "Highway 42"},
        )
        conn.fetch_one("SELECT * FROM customers")
        assert len(conn._unique_results) == 1
        conn.reset_connections()
        assert len(conn._unique_results) == 0

    def test_flow_without_initialized_engine(self, tmp_path):
        @task
        def setup_table(block_name: str) -> None:
            with SqlAlchemyConnector.load(block_name) as connector:
                connector.execute(
                    "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"  # noqa
                )
                connector.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
                connector.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Highway 42"},
                    ],
                )

        @task
        def fetch_data(block_name: str) -> list:
            all_rows = []
            with SqlAlchemyConnector.load(block_name) as connector:
                while True:
                    # Repeated fetch* calls using the same operation will
                    # skip re-executing and instead return the next set of results
                    new_rows = connector.fetch_many("SELECT * FROM customers", size=2)
                    if len(new_rows) == 0:
                        break
                    all_rows.append(new_rows)
            return all_rows

        @flow
        def sqlalchemy_flow(block_name: str) -> list:
            SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                    driver=SyncDriver.SQLITE_PYSQLITE,
                    database=str(tmp_path / "test.db"),
                )
            ).save(block_name)
            setup_table(block_name)
            all_rows = fetch_data(block_name)
            return all_rows

        assert sqlalchemy_flow("connector") == [
            [("Marvin", "Highway 42"), ("Ford", "Highway 42")],
            [("Unknown", "Highway 42")],
        ]
