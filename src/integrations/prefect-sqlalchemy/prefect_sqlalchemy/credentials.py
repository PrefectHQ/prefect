"""Credential classes used to perform authenticated interactions with SQLAlchemy"""

import warnings
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.core import Block

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import AnyUrl, BaseModel, Field, SecretStr
else:
    from pydantic import AnyUrl, BaseModel, Field, SecretStr

from sqlalchemy.engine import Connection, create_engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool


class AsyncDriver(Enum):
    """
    Known dialects with their corresponding async drivers.

    Attributes:
        POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)

        SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)

        MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)
        MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)
    """  # noqa

    POSTGRESQL_ASYNCPG = "postgresql+asyncpg"

    SQLITE_AIOSQLITE = "sqlite+aiosqlite"

    MYSQL_ASYNCMY = "mysql+asyncmy"
    MYSQL_AIOMYSQL = "mysql+aiomysql"


class SyncDriver(Enum):
    """
    Known dialects with their corresponding sync drivers.

    Attributes:
        POSTGRESQL_PSYCOPG2 (Enum): [postgresql+psycopg2](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2)
        POSTGRESQL_PG8000 (Enum): [postgresql+pg8000](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pg8000)
        POSTGRESQL_PSYCOPG2CFFI (Enum): [postgresql+psycopg2cffi](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2cffi)
        POSTGRESQL_PYPOSTGRESQL (Enum): [postgresql+pypostgresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pypostgresql)
        POSTGRESQL_PYGRESQL (Enum): [postgresql+pygresql](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.pygresql)

        MYSQL_MYSQLDB (Enum): [mysql+mysqldb](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)
        MYSQL_PYMYSQL (Enum): [mysql+pymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql)
        MYSQL_MYSQLCONNECTOR (Enum): [mysql+mysqlconnector](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqlconnector)
        MYSQL_CYMYSQL (Enum): [mysql+cymysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.cymysql)
        MYSQL_OURSQL (Enum): [mysql+oursql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.oursql)
        MYSQL_PYODBC (Enum): [mysql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pyodbc)

        SQLITE_PYSQLITE (Enum): [sqlite+pysqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlite)
        SQLITE_PYSQLCIPHER (Enum): [sqlite+pysqlcipher](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.pysqlcipher)

        ORACLE_CX_ORACLE (Enum): [oracle+cx_oracle](https://docs.sqlalchemy.org/en/14/dialects/oracle.html#module-sqlalchemy.dialects.oracle.cx_oracle)

        MSSQL_PYODBC (Enum): [mssql+pyodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)
        MSSQL_MXODBC (Enum): [mssql+mxodbc](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.mxodbc)
        MSSQL_PYMSSQL (Enum): [mssql+pymssql](https://docs.sqlalchemy.org/en/14/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pymssql)
    """  # noqa

    POSTGRESQL_PSYCOPG2 = "postgresql+psycopg2"
    POSTGRESQL_PG8000 = "postgresql+pg8000"
    POSTGRESQL_PSYCOPG2CFFI = "postgresql+psycopg2cffi"
    POSTGRESQL_PYPOSTGRESQL = "postgresql+pypostgresql"
    POSTGRESQL_PYGRESQL = "postgresql+pygresql"

    MYSQL_MYSQLDB = "mysql+mysqldb"
    MYSQL_PYMYSQL = "mysql+pymysql"
    MYSQL_MYSQLCONNECTOR = "mysql+mysqlconnector"
    MYSQL_CYMYSQL = "mysql+cymysql"
    MYSQL_OURSQL = "mysql+oursql"
    MYSQL_PYODBC = "mysql+pyodbc"

    SQLITE_PYSQLITE = "sqlite+pysqlite"
    SQLITE_PYSQLCIPHER = "sqlite+pysqlcipher"

    ORACLE_CX_ORACLE = "oracle+cx_oracle"

    MSSQL_PYODBC = "mssql+pyodbc"
    MSSQL_MXODBC = "mssql+mxodbc"
    MSSQL_PYMSSQL = "mssql+pymssql"


class ConnectionComponents(BaseModel):
    """
    Parameters to use to create a SQLAlchemy engine URL.

    Attributes:
        driver: The driver name to use.
        database: The name of the database to use.
        username: The user name used to authenticate.
        password: The password used to authenticate.
        host: The host address of the database.
        port: The port to connect to the database.
        query: A dictionary of string keys to string values to be passed to the dialect
            and/or the DBAPI upon connect.
    """

    driver: Union[AsyncDriver, SyncDriver, str] = Field(
        default=..., description="The driver name to use."
    )
    database: str = Field(default=..., description="The name of the database to use.")
    username: Optional[str] = Field(
        default=None, description="The user name used to authenticate."
    )
    password: Optional[SecretStr] = Field(
        default=None, description="The password used to authenticate."
    )
    host: Optional[str] = Field(
        default=None, description="The host address of the database."
    )
    port: Optional[str] = Field(
        default=None, description="The port to connect to the database."
    )
    query: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "A dictionary of string keys to string values to be passed to the dialect "
            "and/or the DBAPI upon connect. To specify non-string parameters to a "
            "Python DBAPI directly, use connect_args."
        ),
    )

    def create_url(self) -> URL:
        """
        Create a fully formed connection URL.

        Returns:
            The SQLAlchemy engine URL.
        """
        driver = self.driver
        drivername = driver.value if isinstance(driver, Enum) else driver
        password = self.password.get_secret_value() if self.password else None
        url_params = dict(
            drivername=drivername,
            username=self.username,
            password=password,
            database=self.database,
            host=self.host,
            port=self.port,
            query=self.query,
        )
        return URL.create(
            **{
                url_key: url_param
                for url_key, url_param in url_params.items()
                if url_param is not None
            }
        )


class DatabaseCredentials(Block):
    """
    Block used to manage authentication with a database.

    Attributes:
        driver: The driver name, e.g. "postgresql+asyncpg"
        database: The name of the database to use.
        username: The user name used to authenticate.
        password: The password used to authenticate.
        host: The host address of the database.
        port: The port to connect to the database.
        query: A dictionary of string keys to string values to be passed to
            the dialect and/or the DBAPI upon connect. To specify non-string
            parameters to a Python DBAPI directly, use connect_args.
        url: Manually create and provide a URL to create the engine,
            this is useful for external dialects, e.g. Snowflake, because some
            of the params, such as "warehouse", is not directly supported in
            the vanilla `sqlalchemy.engine.URL.create` method; do not provide
            this alongside with other URL params as it will raise a `ValueError`.
        connect_args: The options which will be passed directly to the
            DBAPI's connect() method as additional keyword arguments.

    Example:
        Load stored database credentials:
        ```python
        from prefect_sqlalchemy import DatabaseCredentials
        database_block = DatabaseCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Database Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/fb3f4debabcda1c5a3aeea4f5b3f94c28845e23e-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-sqlalchemy/credentials/#prefect_sqlalchemy.credentials.DatabaseCredentials"  # noqa

    driver: Optional[Union[AsyncDriver, SyncDriver, str]] = Field(
        default=None, description="The driver name to use."
    )
    username: Optional[str] = Field(
        default=None, description="The user name used to authenticate."
    )
    password: Optional[SecretStr] = Field(
        default=None, description="The password used to authenticate."
    )
    database: Optional[str] = Field(
        default=None, description="The name of the database to use."
    )
    host: Optional[str] = Field(
        default=None, description="The host address of the database."
    )
    port: Optional[str] = Field(
        default=None, description="The port to connect to the database."
    )
    query: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "A dictionary of string keys to string values to be passed to the dialect "
            "and/or the DBAPI upon connect. To specify non-string parameters to a "
            "Python DBAPI directly, use connect_args."
        ),
    )
    url: Optional[AnyUrl] = Field(
        default=None,
        description=(
            "Manually create and provide a URL to create the engine, this is useful "
            "for external dialects, e.g. Snowflake, because some of the params, "
            "such as 'warehouse', is not directly supported in the vanilla "
            "`sqlalchemy.engine.URL.create` method; do not provide this "
            "alongside with other URL params as it will raise a `ValueError`."
        ),
    )
    connect_args: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "The options which will be passed directly to the DBAPI's connect() "
            "method as additional keyword arguments."
        ),
    )

    def block_initialization(self):
        """
        Initializes the engine.
        """
        warnings.warn(
            "DatabaseCredentials is now deprecated and will be removed March 2023; "
            "please use SqlAlchemyConnector instead.",
            DeprecationWarning,
        )
        if isinstance(self.driver, AsyncDriver):
            drivername = self.driver.value
            self._driver_is_async = True
        elif isinstance(self.driver, SyncDriver):
            drivername = self.driver.value
            self._driver_is_async = False
        else:
            drivername = self.driver
            self._driver_is_async = drivername in AsyncDriver._value2member_map_

        url_params = dict(
            drivername=drivername,
            username=self.username,
            password=self.password.get_secret_value() if self.password else None,
            database=self.database,
            host=self.host,
            port=self.port,
            query=self.query,
        )
        if not self.url:
            required_url_keys = ("drivername", "database")
            if not all(url_params[key] for key in required_url_keys):
                required_url_keys = ("driver", "database")
                raise ValueError(
                    f"If the `url` is not provided, "
                    f"all of these URL params are required: "
                    f"{required_url_keys}"
                )
            self.rendered_url = URL.create(
                **{
                    url_key: url_param
                    for url_key, url_param in url_params.items()
                    if url_param is not None
                }
            )  # from params
        else:
            if any(val for val in url_params.values()):
                raise ValueError(
                    f"The `url` should not be provided "
                    f"alongside any of these URL params: "
                    f"{url_params.keys()}"
                )
            self.rendered_url = make_url(str(self.url))

    def get_engine(self) -> Union["Connection", "AsyncConnection"]:
        """
        Returns an authenticated engine that can be
        used to query from databases.

        Returns:
            The authenticated SQLAlchemy Connection / AsyncConnection.

        Examples:
            Create an asynchronous engine to PostgreSQL using URL params.
            ```python
            from prefect import flow
            from prefect_sqlalchemy import DatabaseCredentials, AsyncDriver

            @flow
            def sqlalchemy_credentials_flow():
                sqlalchemy_credentials = DatabaseCredentials(
                    driver=AsyncDriver.POSTGRESQL_ASYNCPG,
                    username="prefect",
                    password="prefect_password",
                    database="postgres"
                )
                print(sqlalchemy_credentials.get_engine())

            sqlalchemy_credentials_flow()
            ```

            Create a synchronous engine to Snowflake using the `url` kwarg.
            ```python
            from prefect import flow
            from prefect_sqlalchemy import DatabaseCredentials, AsyncDriver

            @flow
            def sqlalchemy_credentials_flow():
                url = (
                    "snowflake://<user_login_name>:<password>"
                    "@<account_identifier>/<database_name>"
                    "?warehouse=<warehouse_name>"
                )
                sqlalchemy_credentials = DatabaseCredentials(url=url)
                print(sqlalchemy_credentials.get_engine())

            sqlalchemy_credentials_flow()
            ```
        """
        engine_kwargs = dict(
            url=self.rendered_url,
            connect_args=self.connect_args or {},
            poolclass=NullPool,
        )
        if self._driver_is_async:
            engine = create_async_engine(**engine_kwargs)
        else:
            engine = create_engine(**engine_kwargs)
        return engine

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
        d["rendered_url"] = SecretStr(
            self.rendered_url.render_as_string(hide_password=False)
        )
        return d
