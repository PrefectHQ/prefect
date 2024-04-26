"""Tasks for querying a database with SQLAlchemy"""

import contextlib
import warnings
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import VERSION as PYDANTIC_VERSION

from prefect import task
from prefect.blocks.abstract import CredentialsBlock, DatabaseBlock
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.hashing import hash_objects

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import AnyUrl, Field, SecretStr
else:
    from pydantic import AnyUrl, Field, SecretStr

from sqlalchemy import __version__ as SQLALCHEMY_VERSION
from sqlalchemy.engine import Connection, Engine, create_engine
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.sql import text
from typing_extensions import Literal

from prefect_sqlalchemy.credentials import (
    AsyncDriver,
    ConnectionComponents,
    DatabaseCredentials,
)


@contextlib.asynccontextmanager
async def _connect(
    engine: Union["AsyncEngine", "Engine"],
    async_supported: bool,
) -> Union["AsyncConnection", "Connection"]:
    """
    Helper method to create a connection to the database, either
    synchronously or asynchronously.
    """
    try:
        # a context manager nested within a context manager!
        if async_supported:
            async with engine.connect() as connection:
                yield connection
        else:
            with engine.connect() as connection:
                yield connection
    finally:
        dispose = engine.dispose()
        if async_supported:
            await dispose


async def _execute(
    connection: Union["AsyncConnection", "Connection"],
    query: str,
    params: Optional[Union[Tuple[Any], Dict[str, Any]]],
    async_supported: bool,
) -> "CursorResult":
    """
    Helper method to execute database queries or statements, either
    synchronously or asynchronously.
    """
    result = connection.execute(text(query), params)
    if async_supported:
        result = await result
        await connection.commit()
    elif SQLALCHEMY_VERSION.startswith("2."):
        connection.commit()
    return result


@task
async def sqlalchemy_execute(
    statement: str,
    sqlalchemy_credentials: "DatabaseCredentials",
    params: Optional[Union[Tuple[Any], Dict[str, Any]]] = None,
):
    """
    Executes a SQL DDL or DML statement; useful for creating tables and inserting rows
    since this task does not return any objects.

    Args:
        statement: The statement to execute against the database.
        sqlalchemy_credentials: The credentials to use to authenticate.
        params: The params to replace the placeholders in the query.

    Examples:
        Create table named customers and insert values.
        ```python
        from prefect_sqlalchemy import DatabaseCredentials, AsyncDriver
        from prefect_sqlalchemy.database import sqlalchemy_execute
        from prefect import flow

        @flow
        def sqlalchemy_execute_flow():
            sqlalchemy_credentials = DatabaseCredentials(
                driver=AsyncDriver.SQLITE_AIOSQLITE,
                database="prefect.db",
            )
            sqlalchemy_execute(
                "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);",
                sqlalchemy_credentials,
            )
            sqlalchemy_execute(
                "INSERT INTO customers (name, address) VALUES (:name, :address);",
                sqlalchemy_credentials,
                params={"name": "Marvin", "address": "Highway 42"}
            )

        sqlalchemy_execute_flow()
        ```
    """
    warnings.warn(
        "sqlalchemy_query is now deprecated and will be removed March 2023; "
        "please use SqlAlchemyConnector execute_* methods instead.",
        DeprecationWarning,
    )
    # do not return anything or else results in the error:
    # This result object does not return rows. It has been closed automatically
    engine = sqlalchemy_credentials.get_engine()
    async_supported = sqlalchemy_credentials._driver_is_async
    async with _connect(engine, async_supported) as connection:
        await _execute(connection, statement, params, async_supported)


@task
async def sqlalchemy_query(
    query: str,
    sqlalchemy_credentials: "DatabaseCredentials",
    params: Optional[Union[Tuple[Any], Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> List[Tuple[Any]]:
    """
    Executes a SQL query; useful for querying data from existing tables.

    Args:
        query: The query to execute against the database.
        sqlalchemy_credentials: The credentials to use to authenticate.
        params: The params to replace the placeholders in the query.
        limit: The number of rows to fetch. Note, this parameter is
            executed on the client side, i.e. passed to `fetchmany`.
            To limit on the server side, add the `LIMIT` clause, or
            the dialect's equivalent clause, like `TOP`, to the query.

    Returns:
        The fetched results.

    Examples:
        Query postgres table with the ID value parameterized.
        ```python
        from prefect_sqlalchemy import DatabaseCredentials, AsyncDriver
        from prefect_sqlalchemy.database import sqlalchemy_query
        from prefect import flow

        @flow
        def sqlalchemy_query_flow():
            sqlalchemy_credentials = DatabaseCredentials(
                driver=AsyncDriver.SQLITE_AIOSQLITE,
                database="prefect.db",
            )
            result = sqlalchemy_query(
                "SELECT * FROM customers WHERE name = :name;",
                sqlalchemy_credentials,
                params={"name": "Marvin"},
            )
            return result

        sqlalchemy_query_flow()
        ```
    """
    warnings.warn(
        "sqlalchemy_query is now deprecated and will be removed March 2023; "
        "please use SqlAlchemyConnector fetch_* methods instead.",
        DeprecationWarning,
    )
    engine = sqlalchemy_credentials.get_engine()
    async_supported = sqlalchemy_credentials._driver_is_async
    async with _connect(engine, async_supported) as connection:
        result = await _execute(connection, query, params, async_supported)
        # some databases, like sqlite, require a connection still open to fetch!
        rows = result.fetchall() if limit is None else result.fetchmany(limit)
    return rows


class SqlAlchemyConnector(CredentialsBlock, DatabaseBlock):
    """
    Block used to manage authentication with a database.

    Upon instantiating, an engine is created and maintained for the life of
    the object until the close method is called.

    It is recommended to use this block as a context manager, which will automatically
    close the engine and its connections when the context is exited.

    It is also recommended that this block is loaded and consumed within a single task
    or flow because if the block is passed across separate tasks and flows,
    the state of the block's connection and cursor could be lost.

    Attributes:
        connection_info: SQLAlchemy URL to create the engine;
            either create from components or create from a string.
        connect_args: The options which will be passed directly to the
            DBAPI's connect() method as additional keyword arguments.
        fetch_size: The number of rows to fetch at a time.

    Example:
        Load stored database credentials and use in context manager:
        ```python
        from prefect_sqlalchemy import SqlAlchemyConnector

        database_block = SqlAlchemyConnector.load("BLOCK_NAME")
        with database_block:
            ...
        ```

        Create table named customers and insert values; then fetch the first 10 rows.
        ```python
        from prefect_sqlalchemy import (
            SqlAlchemyConnector, SyncDriver, ConnectionComponents
        )

        with SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver=SyncDriver.SQLITE_PYSQLITE,
                database="prefect.db"
            )
        ) as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);",
            )
            for i in range(1, 42):
                database.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": f"Highway {i}"},
                )
            results = database.fetch_many(
                "SELECT * FROM customers WHERE name = :name;",
                parameters={"name": "Marvin"},
                size=10
            )
        print(results)
        ```
    """

    _block_type_name = "SQLAlchemy Connector"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/3c7dff04f70aaf4528e184a3b028f9e40b98d68c-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-sqlalchemy/database/#prefect_sqlalchemy.database.SqlAlchemyConnector"  # noqa

    connection_info: Union[ConnectionComponents, AnyUrl] = Field(
        default=...,
        description=(
            "SQLAlchemy URL to create the engine; either create from components "
            "or create from a string."
        ),
    )
    connect_args: Optional[Dict[str, Any]] = Field(
        default=None,
        title="Additional Connection Arguments",
        description=(
            "The options which will be passed directly to the DBAPI's connect() "
            "method as additional keyword arguments."
        ),
    )
    fetch_size: int = Field(
        default=1, description="The number of rows to fetch at a time."
    )

    _engine: Optional[Union[AsyncEngine, Engine]] = None
    _exit_stack: Union[ExitStack, AsyncExitStack] = None
    _unique_results: Dict[str, CursorResult] = None

    class Config:
        """Configuration of pydantic."""

        # Support serialization of the 'URL' type
        arbitrary_types_allowed = True
        json_encoders = {URL: lambda u: u.render_as_string()}

    def dict(self, *args, **kwargs) -> Dict:
        """
        Convert to a dictionary.
        """
        # Support serialization of the 'URL' type
        d = super().dict(*args, **kwargs)
        d["_rendered_url"] = SecretStr(
            self._rendered_url.render_as_string(hide_password=False)
        )
        return d

    def block_initialization(self):
        """
        Initializes the engine.
        """
        super().block_initialization()

        if isinstance(self.connection_info, ConnectionComponents):
            self._rendered_url = self.connection_info.create_url()
        else:
            # make rendered url from string
            self._rendered_url = make_url(str(self.connection_info))
        drivername = self._rendered_url.drivername

        try:
            AsyncDriver(drivername)
            self._driver_is_async = True
        except ValueError:
            self._driver_is_async = False

        if self._unique_results is None:
            self._unique_results = {}

        if self._exit_stack is None:
            self._start_exit_stack()

    def _start_exit_stack(self):
        """
        Starts an AsyncExitStack or ExitStack depending on whether driver is async.
        """
        self._exit_stack = AsyncExitStack() if self._driver_is_async else ExitStack()

    def get_engine(
        self, **create_engine_kwargs: Dict[str, Any]
    ) -> Union[Engine, AsyncEngine]:
        """
        Returns an authenticated engine that can be
        used to query from databases.

        If an existing engine exists, return that one.

        Returns:
            The authenticated SQLAlchemy Engine / AsyncEngine.

        Examples:
            Create an asynchronous engine to PostgreSQL using URL params.
            ```python
            from prefect import flow
            from prefect_sqlalchemy import (
                SqlAlchemyConnector, ConnectionComponents, AsyncDriver
            )

            @flow
            def sqlalchemy_credentials_flow():
                sqlalchemy_credentials = SqlAlchemyConnector(
                connection_info=ConnectionComponents(
                        driver=AsyncDriver.POSTGRESQL_ASYNCPG,
                        username="prefect",
                        password="prefect_password",
                        database="postgres"
                    )
                )
                print(sqlalchemy_credentials.get_engine())

            sqlalchemy_credentials_flow()
            ```

            Create a synchronous engine to Snowflake using the `url` kwarg.
            ```python
            from prefect import flow
            from prefect_sqlalchemy import SqlAlchemyConnector, AsyncDriver

            @flow
            def sqlalchemy_credentials_flow():
                url = (
                    "snowflake://<user_login_name>:<password>"
                    "@<account_identifier>/<database_name>"
                    "?warehouse=<warehouse_name>"
                )
                sqlalchemy_credentials = SqlAlchemyConnector(url=url)
                print(sqlalchemy_credentials.get_engine())

            sqlalchemy_credentials_flow()
            ```
        """
        if self._engine is not None:
            self.logger.debug("Reusing existing engine.")
            return self._engine

        engine_kwargs = dict(
            url=self._rendered_url,
            connect_args=self.connect_args or {},
            **create_engine_kwargs,
        )
        if self._driver_is_async:
            # no need to await here
            engine = create_async_engine(**engine_kwargs)
        else:
            engine = create_engine(**engine_kwargs)
        self.logger.info("Created a new engine.")

        if self._engine is None:
            self._engine = engine

        return engine

    def get_connection(
        self, begin: bool = True, **connect_kwargs: Dict[str, Any]
    ) -> Union[Connection, AsyncConnection]:
        """
        Returns a connection that can be used to query from databases.

        Args:
            begin: Whether to begin a transaction on the connection; if True, if
                any operations fail, the entire transaction will be rolled back.
            **connect_kwargs: Additional keyword arguments to pass to either
                `engine.begin` or engine.connect`.

        Returns:
            The SQLAlchemy Connection / AsyncConnection.

        Examples:
            Create an synchronous connection as a context-managed transaction.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            sqlalchemy_connector = SqlAlchemyConnector.load("BLOCK_NAME")
            with sqlalchemy_connector.get_connection(begin=False) as connection:
                connection.execute("SELECT * FROM table LIMIT 1;")
            ```

            Create an asynchronous connection as a context-managed transacation.
            ```python
            import asyncio
            from prefect_sqlalchemy import SqlAlchemyConnector

            sqlalchemy_connector = SqlAlchemyConnector.load("BLOCK_NAME")
            async with sqlalchemy_connector.get_connection(begin=False) as connection:
                asyncio.run(connection.execute("SELECT * FROM table LIMIT 1;"))
            ```
        """  # noqa: E501
        engine = self.get_engine()
        if begin:
            connection = engine.begin(**connect_kwargs)
        else:
            connection = engine.connect(**connect_kwargs)
        self.logger.info("Created a new connection.")
        return connection

    def get_client(
        self,
        client_type: Literal["engine", "connection"],
        **get_client_kwargs: Dict[str, Any],
    ) -> Union[Engine, AsyncEngine, Connection, AsyncConnection]:
        """
        Returns either an engine or connection that can be used to query from databases.

        Args:
            client_type: Select from either 'engine' or 'connection'.
            **get_client_kwargs: Additional keyword arguments to pass to
                either `get_engine` or `get_connection`.

        Returns:
            The authenticated SQLAlchemy engine or connection.

        Examples:
            Create an engine.
            ```python
            from prefect_sqlalchemy import SqlalchemyConnector

            sqlalchemy_connector = SqlAlchemyConnector.load("BLOCK_NAME")
            engine = sqlalchemy_connector.get_client(client_type="engine")
            ```

            Create a context managed connection.
            ```python
            from prefect_sqlalchemy import SqlalchemyConnector

            sqlalchemy_connector = SqlAlchemyConnector.load("BLOCK_NAME")
            with sqlalchemy_connector.get_client(client_type="connection") as conn:
                ...
            ```
        """  # noqa: E501
        if client_type == "engine":
            client = self.get_engine(**get_client_kwargs)
        elif client_type == "connection":
            client = self.get_connection(**get_client_kwargs)
        else:
            raise ValueError(
                f"{client_type!r} is not supported; choose from engine or connection."
            )
        return client

    async def _async_sync_execute(
        self,
        connection: Union[Connection, AsyncConnection],
        *execute_args: Tuple[Any],
        **execute_kwargs: Dict[str, Any],
    ) -> CursorResult:
        """
        Execute the statement asynchronously or synchronously.
        """
        # can't use run_sync_in_worker_thread:
        # ProgrammingError: (sqlite3.ProgrammingError) SQLite objects created in a
        # thread can only be used in that same thread.
        result_set = connection.execute(*execute_args, **execute_kwargs)

        if self._driver_is_async:
            result_set = await result_set
            await connection.commit()  # very important
        elif SQLALCHEMY_VERSION.startswith("2."):
            connection.commit()
        return result_set

    @asynccontextmanager
    async def _manage_connection(self, **get_connection_kwargs: Dict[str, Any]):
        if self._driver_is_async:
            async with self.get_connection(**get_connection_kwargs) as connection:
                yield connection
        else:
            with self.get_connection(**get_connection_kwargs) as connection:
                yield connection

    async def _get_result_set(
        self, *execute_args: Tuple[Any], **execute_kwargs: Dict[str, Any]
    ) -> CursorResult:
        """
        Returns a new or existing result set based on whether the inputs
        are unique.

        Args:
            *execute_args: Args to pass to execute.
            **execute_kwargs: Keyword args to pass to execute.

        Returns:
            The result set from the operation.
        """  # noqa: E501
        input_hash = hash_objects(*execute_args, **execute_kwargs)
        assert input_hash is not None, (
            "We were not able to hash your inputs, "
            "which resulted in an unexpected data return; "
            "please open an issue with a reproducible example."
        )

        if input_hash not in self._unique_results.keys():
            if self._driver_is_async:
                connection = await self._exit_stack.enter_async_context(
                    self.get_connection()
                )
            else:
                connection = self._exit_stack.enter_context(self.get_connection())
            result_set = await self._async_sync_execute(
                connection, *execute_args, **execute_kwargs
            )
            # implicitly store the connection by storing the result set
            # which points to its parent connection
            self._unique_results[input_hash] = result_set
        else:
            result_set = self._unique_results[input_hash]
        return result_set

    def _reset_cursor_results(self) -> None:
        """
        Closes all the existing cursor results.
        """
        input_hashes = tuple(self._unique_results.keys())
        for input_hash in input_hashes:
            try:
                cursor_result = self._unique_results.pop(input_hash)
                cursor_result.close()
            except Exception as exc:
                self.logger.warning(
                    f"Failed to close connection for input hash {input_hash!r}: {exc}"
                )

    @sync_compatible
    async def reset_connections(self) -> None:
        """
        Tries to close all opened connections and their results.

        Examples:
            Resets connections so `fetch_*` methods return new results.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                results = database.fetch_one("SELECT * FROM customers")
                database.reset_connections()
                results = database.fetch_one("SELECT * FROM customers")
            ```
        """
        if self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} has no synchronous connections. "
                f"Please use the `reset_async_connections` method instead."
            )

        if self._exit_stack is None:
            self.logger.info("There were no connections to reset.")
            return

        self._reset_cursor_results()
        self._exit_stack.close()
        self.logger.info("Reset opened connections and their results.")

    async def reset_async_connections(self) -> None:
        """
        Tries to close all opened connections and their results.

        Examples:
            Resets connections so `fetch_*` methods return new results.
            ```python
            import asyncio
            from prefect_sqlalchemy import SqlAlchemyConnector

            async def example_run():
                async with SqlAlchemyConnector.load("MY_BLOCK") as database:
                    results = await database.fetch_one("SELECT * FROM customers")
                    await database.reset_async_connections()
                    results = await database.fetch_one("SELECT * FROM customers")

            asyncio.run(example_run())
            ```
        """
        if not self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} has no asynchronous connections. "
                f"Please use the `reset_connections` method instead."
            )

        if self._exit_stack is None:
            self.logger.info("There were no connections to reset.")
            return

        self._reset_cursor_results()
        await self._exit_stack.aclose()
        self.logger.info("Reset opened connections and their results.")

    @sync_compatible
    async def fetch_one(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        **execution_options: Dict[str, Any],
    ) -> Tuple[Any]:
        """
        Fetch a single result from the database.

        Repeated calls using the same inputs to *any* of the fetch methods of this
        block will skip executing the operation again, and instead,
        return the next set of results from the previous execution,
        until the reset_cursors method is called.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_options: Options to pass to `Connection.execution_options`.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.

        Examples:
            Create a table, insert three rows into it, and fetch a row repeatedly.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                database.execute("CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);")
                database.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                        {"name": "Me", "address": "Myway 88"},
                    ],
                )
                results = True
                while results:
                    results = database.fetch_one("SELECT * FROM customers")
                    print(results)
            ```
        """  # noqa
        result_set = await self._get_result_set(
            text(operation), parameters, execution_options=execution_options
        )
        self.logger.debug("Preparing to fetch one row.")
        row = result_set.fetchone()
        return row

    @sync_compatible
    async def fetch_many(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        size: Optional[int] = None,
        **execution_options: Dict[str, Any],
    ) -> List[Tuple[Any]]:
        """
        Fetch a limited number of results from the database.

        Repeated calls using the same inputs to *any* of the fetch methods of this
        block will skip executing the operation again, and instead,
        return the next set of results from the previous execution,
        until the reset_cursors method is called.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            size: The number of results to return; if None or 0, uses the value of
                `fetch_size` configured on the block.
            **execution_options: Options to pass to `Connection.execution_options`.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.

        Examples:
            Create a table, insert three rows into it, and fetch two rows repeatedly.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                database.execute("CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);")
                database.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                        {"name": "Me", "address": "Myway 88"},
                    ],
                )
                results = database.fetch_many("SELECT * FROM customers", size=2)
                print(results)
                results = database.fetch_many("SELECT * FROM customers", size=2)
                print(results)
            ```
        """  # noqa
        result_set = await self._get_result_set(
            text(operation), parameters, execution_options=execution_options
        )
        size = size or self.fetch_size
        self.logger.debug(f"Preparing to fetch {size} rows.")
        rows = result_set.fetchmany(size=size)
        return rows

    @sync_compatible
    async def fetch_all(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        **execution_options: Dict[str, Any],
    ) -> List[Tuple[Any]]:
        """
        Fetch all results from the database.

        Repeated calls using the same inputs to *any* of the fetch methods of this
        block will skip executing the operation again, and instead,
        return the next set of results from the previous execution,
        until the reset_cursors method is called.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_options: Options to pass to `Connection.execution_options`.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.

        Examples:
            Create a table, insert three rows into it, and fetch all where name is 'Me'.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                database.execute("CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);")
                database.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                        {"name": "Me", "address": "Myway 88"},
                    ],
                )
                results = database.fetch_all("SELECT * FROM customers WHERE name = :name", parameters={"name": "Me"})
            ```
        """  # noqa
        result_set = await self._get_result_set(
            text(operation), parameters, execution_options=execution_options
        )
        self.logger.debug("Preparing to fetch all rows.")
        rows = result_set.fetchall()
        return rows

    @sync_compatible
    async def execute(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        **execution_options: Dict[str, Any],
    ) -> None:
        """
        Executes an operation on the database. This method is intended to be used
        for operations that do not return data, such as INSERT, UPDATE, or DELETE.

        Unlike the fetch methods, this method will always execute the operation
        upon calling.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_options: Options to pass to `Connection.execution_options`.

        Examples:
            Create a table and insert one row into it.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                database.execute("CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);")
                database.execute(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    parameters={"name": "Marvin", "address": "Highway 42"},
                )
            ```
        """  # noqa
        async with self._manage_connection(begin=False) as connection:
            await self._async_sync_execute(
                connection,
                text(operation),
                parameters,
                execution_options=execution_options,
            )
        self.logger.info(f"Executed the operation, {operation!r}")

    @sync_compatible
    async def execute_many(
        self,
        operation: str,
        seq_of_parameters: List[Dict[str, Any]],
        **execution_options: Dict[str, Any],
    ) -> None:
        """
        Executes many operations on the database. This method is intended to be used
        for operations that do not return data, such as INSERT, UPDATE, or DELETE.

        Unlike the fetch methods, this method will always execute the operation
        upon calling.

        Args:
            operation: The SQL query or other operation to be executed.
            seq_of_parameters: The sequence of parameters for the operation.
            **execution_options: Options to pass to `Connection.execution_options`.

        Examples:
            Create a table and insert two rows into it.
            ```python
            from prefect_sqlalchemy import SqlAlchemyConnector

            with SqlAlchemyConnector.load("MY_BLOCK") as database:
                database.execute("CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);")
                database.execute_many(
                    "INSERT INTO customers (name, address) VALUES (:name, :address);",
                    seq_of_parameters=[
                        {"name": "Ford", "address": "Highway 42"},
                        {"name": "Unknown", "address": "Space"},
                        {"name": "Me", "address": "Myway 88"},
                    ],
                )
            ```
        """  # noqa
        async with self._manage_connection(begin=False) as connection:
            await self._async_sync_execute(
                connection,
                text(operation),
                seq_of_parameters,
                execution_options=execution_options,
            )
        self.logger.info(
            f"Executed {len(seq_of_parameters)} operations based off {operation!r}."
        )

    async def __aenter__(self):
        """
        Start an asynchronous database engine upon entry.
        """
        if not self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} cannot be run asynchronously. "
                f"Please use the `with` syntax."
            )
        return self

    async def __aexit__(self, *args):
        """
        Dispose the asynchronous database engine upon exit.
        """
        await self.aclose()

    async def aclose(self):
        """
        Closes async connections and its cursors.
        """
        if not self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} is not asynchronous. "
                f"Please use the `close` method instead."
            )
        try:
            await self.reset_async_connections()
        finally:
            if self._engine is not None:
                await self._engine.dispose()
                self._engine = None
                self.logger.info("Disposed the engine.")

    def __enter__(self):
        """
        Start an synchronous database engine upon entry.
        """
        if self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} cannot be run synchronously. "
                f"Please use the `async with` syntax."
            )
        return self

    def __exit__(self, *args):
        """
        Dispose the synchronous database engine upon exit.
        """
        self.close()

    def close(self):
        """
        Closes sync connections and its cursors.
        """
        if self._driver_is_async:
            raise RuntimeError(
                f"{self._rendered_url.drivername} is not synchronous. "
                f"Please use the `aclose` method instead."
            )

        try:
            self.reset_connections()
        finally:
            if self._engine is not None:
                self._engine.dispose()
                self._engine = None
                self.logger.info("Disposed the engine.")

    def __getstate__(self):
        """Allows the block to be pickleable."""
        data = self.__dict__.copy()
        data.update({k: None for k in {"_engine", "_exit_stack", "_unique_results"}})
        return data

    def __setstate__(self, data: dict):
        """Upon loading back, restart the engine and results."""
        self.__dict__.update(data)

        if self._unique_results is None:
            self._unique_results = {}

        if self._exit_stack is None:
            self._start_exit_stack()
