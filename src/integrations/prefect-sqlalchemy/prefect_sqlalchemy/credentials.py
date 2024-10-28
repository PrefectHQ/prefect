"""Credential classes used to perform authenticated interactions with SQLAlchemy"""

from enum import Enum
from typing import Dict, Optional, Union

from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine.url import URL


class AsyncDriver(Enum):
    """
    Known dialects with their corresponding async drivers.

    Attributes:
        POSTGRESQL_ASYNCPG (Enum): [postgresql+asyncpg](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)

        SQLITE_AIOSQLITE (Enum): [sqlite+aiosqlite](https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#module-sqlalchemy.dialects.sqlite.aiosqlite)

        MYSQL_ASYNCMY (Enum): [mysql+asyncmy](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)
        MYSQL_AIOMYSQL (Enum): [mysql+aiomysql](https://docs.sqlalchemy.org/en/14/dialects/mysql.html#module-sqlalchemy.dialects.mysql.aiomysql)

        ORACLE_ORACLEDB_ASYNC (Enum): [oracle+oracledb_async](https://docs.sqlalchemy.org/en/20/dialects/oracle.html#module-sqlalchemy.dialects.oracle.oracledb)
    """  # noqa

    POSTGRESQL_ASYNCPG = "postgresql+asyncpg"

    SQLITE_AIOSQLITE = "sqlite+aiosqlite"

    MYSQL_ASYNCMY = "mysql+asyncmy"
    MYSQL_AIOMYSQL = "mysql+aiomysql"

    ORACLE_ORACLEDB_ASYNC = "oracle+oracledb_async"


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
        ORACLE_ORACLEDB (Enum): [oracle+oracledb](https://docs.sqlalchemy.org/en/20/dialects/oracle.html#module-sqlalchemy.dialects.oracle.oracledb)

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
    ORACLE_ORACLEDB = "oracle+oracledb"

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
    database: Optional[str] = Field(
        default=None, description="The name of the database to use."
    )
    username: Optional[str] = Field(
        default=None, description="The user name used to authenticate."
    )
    password: Optional[SecretStr] = Field(
        default=None, description="The password used to authenticate."
    )
    host: Optional[str] = Field(
        default=None, description="The host address of the database."
    )
    port: Optional[int] = Field(
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
