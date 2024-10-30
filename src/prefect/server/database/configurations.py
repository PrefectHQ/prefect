import sqlite3
import traceback
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop, get_running_loop
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import partial
from typing import Dict, Hashable, Optional, Tuple

import sqlalchemy as sa

try:
    from sqlalchemy import AdaptedConnection
    from sqlalchemy.pool import ConnectionPoolEntry
except ImportError:
    # SQLAlchemy 1.4 equivalents
    from sqlalchemy.pool import _ConnectionFairy as AdaptedConnection
    from sqlalchemy.pool.base import _ConnectionRecord as ConnectionPoolEntry

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from typing_extensions import Literal

from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_TIMEOUT,
    PREFECT_API_DATABASE_ECHO,
    PREFECT_API_DATABASE_TIMEOUT,
    PREFECT_SQLALCHEMY_MAX_OVERFLOW,
    PREFECT_SQLALCHEMY_POOL_SIZE,
    PREFECT_TESTING_UNIT_TEST_MODE,
)
from prefect.utilities.asyncutils import add_event_loop_shutdown_callback

SQLITE_BEGIN_MODE: ContextVar[Optional[str]] = ContextVar(  # novm
    "SQLITE_BEGIN_MODE", default=None
)

ENGINES: Dict[Tuple[AbstractEventLoop, str, bool, float], AsyncEngine] = {}


class ConnectionTracker:
    """A test utility which tracks the connections given out by a connection pool, to
    make it easy to see which connections are currently checked out and open."""

    all_connections: Dict[AdaptedConnection, str]
    open_connections: Dict[AdaptedConnection, str]
    left_field_closes: Dict[AdaptedConnection, str]
    connects: int
    closes: int
    active: bool

    def __init__(self) -> None:
        self.active = False
        self.all_connections = {}
        self.open_connections = {}
        self.left_field_closes = {}
        self.connects = 0
        self.closes = 0

    def track_pool(self, pool: sa.pool.Pool):
        sa.event.listen(pool, "connect", self.on_connect)
        sa.event.listen(pool, "close", self.on_close)
        sa.event.listen(pool, "close_detached", self.on_close_detached)

    def on_connect(
        self,
        adapted_connection: AdaptedConnection,
        connection_record: ConnectionPoolEntry,
    ):
        self.all_connections[adapted_connection] = traceback.format_stack()
        self.open_connections[adapted_connection] = traceback.format_stack()
        self.connects += 1

    def on_close(
        self,
        adapted_connection: AdaptedConnection,
        connection_record: ConnectionPoolEntry,
    ):
        try:
            del self.open_connections[adapted_connection]
        except KeyError:
            self.left_field_closes[adapted_connection] = traceback.format_stack()
        self.closes += 1

    def on_close_detached(
        self,
        adapted_connection: AdaptedConnection,
    ):
        try:
            del self.open_connections[adapted_connection]
        except KeyError:
            self.left_field_closes[adapted_connection] = traceback.format_stack()
        self.closes += 1

    def clear(self):
        self.all_connections.clear()
        self.open_connections.clear()
        self.left_field_closes.clear()
        self.connects = 0
        self.closes = 0


TRACKER: ConnectionTracker = ConnectionTracker()


class BaseDatabaseConfiguration(ABC):
    """
    Abstract base class used to inject database connection configuration into Prefect.

    This configuration is responsible for defining how Prefect REST API creates and manages
    database connections and sessions.
    """

    def __init__(
        self,
        connection_url: str,
        echo: Optional[bool] = None,
        timeout: Optional[float] = None,
        connection_timeout: Optional[float] = None,
        sqlalchemy_pool_size: Optional[int] = None,
        sqlalchemy_max_overflow: Optional[int] = None,
    ):
        self.connection_url = connection_url
        self.echo = echo or PREFECT_API_DATABASE_ECHO.value()
        self.timeout = timeout or PREFECT_API_DATABASE_TIMEOUT.value()
        self.connection_timeout = (
            connection_timeout or PREFECT_API_DATABASE_CONNECTION_TIMEOUT.value()
        )
        self.sqlalchemy_pool_size = (
            sqlalchemy_pool_size or PREFECT_SQLALCHEMY_POOL_SIZE.value()
        )
        self.sqlalchemy_max_overflow = (
            sqlalchemy_max_overflow or PREFECT_SQLALCHEMY_MAX_OVERFLOW.value()
        )

    def _unique_key(self) -> Tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, self.connection_url)

    @abstractmethod
    async def engine(self) -> AsyncEngine:
        """Returns a SqlAlchemy engine"""

    @abstractmethod
    async def session(self, engine: AsyncEngine) -> AsyncSession:
        """
        Retrieves a SQLAlchemy session for an engine.
        """

    @abstractmethod
    async def create_db(self, connection, base_metadata):
        """Create the database"""

    @abstractmethod
    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

    @abstractmethod
    def is_inmemory(self) -> bool:
        """Returns true if database is run in memory"""

    @abstractmethod
    async def begin_transaction(
        self, session: AsyncSession, with_for_update: bool = False
    ):
        """Enter a transaction for a session"""
        pass


class AsyncPostgresConfiguration(BaseDatabaseConfiguration):
    async def engine(self) -> AsyncEngine:
        """Retrieves an async SQLAlchemy engine.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to self.connection_url
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to self.echo
            timeout (float, optional): The database statement timeout, in seconds.
                Defaults to self.timeout

        Returns:
            AsyncEngine: a SQLAlchemy engine
        """

        loop = get_running_loop()

        cache_key = (
            loop,
            self.connection_url,
            self.echo,
            self.timeout,
        )
        if cache_key not in ENGINES:
            # apply database timeout
            kwargs = dict()
            connect_args = dict()

            if self.timeout is not None:
                connect_args["command_timeout"] = self.timeout

            if self.connection_timeout is not None:
                connect_args["timeout"] = self.connection_timeout

            if connect_args:
                kwargs["connect_args"] = connect_args

            if self.sqlalchemy_pool_size is not None:
                kwargs["pool_size"] = self.sqlalchemy_pool_size

            if self.sqlalchemy_max_overflow is not None:
                kwargs["max_overflow"] = self.sqlalchemy_max_overflow

            engine = create_async_engine(
                self.connection_url,
                echo=self.echo,
                # "pre-ping" connections upon checkout to ensure they have not been
                # closed on the server side
                pool_pre_ping=True,
                # Use connections in LIFO order to help reduce connections
                # after spiky load and in general increase the likelihood
                # that a given connection pulled from the pool will be
                # usable.
                pool_use_lifo=True,
                **kwargs,
            )

            if TRACKER.active:
                TRACKER.track_pool(engine.pool)

            ENGINES[cache_key] = engine
            await self.schedule_engine_disposal(cache_key)
        return ENGINES[cache_key]

    async def schedule_engine_disposal(self, cache_key):
        """
        Dispose of an engine once the event loop is closing.

        See caveats at `add_event_loop_shutdown_callback`.

        We attempted to lazily clean up old engines when new engines are created, but
        if the loop the engine is attached to is already closed then the connections
        cannot be cleaned up properly and warnings are displayed.

        Engine disposal should only be important when running the application
        ephemerally. Notably, this is an issue in our tests where many short-lived event
        loops and engines are created which can consume all of the available database
        connection slots. Users operating at a scale where connection limits are
        encountered should be encouraged to use a standalone server.
        """

        async def dispose_engine(cache_key):
            engine = ENGINES.pop(cache_key, None)
            if engine:
                await engine.dispose()

        await add_event_loop_shutdown_callback(partial(dispose_engine, cache_key))

    async def session(self, engine: AsyncEngine) -> AsyncSession:
        """
        Retrieves a SQLAlchemy session for an engine.

        Args:
            engine: a sqlalchemy engine
        """
        return AsyncSession(engine, expire_on_commit=False)

    @asynccontextmanager
    async def begin_transaction(
        self, session: AsyncSession, with_for_update: bool = False
    ):
        # `with_for_update` is for SQLite only. For Postgres, lock the row on read
        # for update instead.
        async with session.begin() as transaction:
            yield transaction

    async def create_db(self, connection, base_metadata):
        """Create the database"""

        await connection.run_sync(base_metadata.create_all)

    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

        await connection.run_sync(base_metadata.drop_all)

    def is_inmemory(self) -> Literal[False]:
        """Returns true if database is run in memory"""

        return False


class AioSqliteConfiguration(BaseDatabaseConfiguration):
    MIN_SQLITE_VERSION = (3, 24, 0)

    async def engine(self) -> AsyncEngine:
        """Retrieves an async SQLAlchemy engine.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to self.connection_url
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to self.echo
            timeout (float, optional): The database statement timeout, in seconds.
                Defaults to self.timeout

        Returns:
            AsyncEngine: a SQLAlchemy engine
        """

        if sqlite3.sqlite_version_info < self.MIN_SQLITE_VERSION:
            required = ".".join(str(v) for v in self.MIN_SQLITE_VERSION)
            raise RuntimeError(
                f"Prefect requires sqlite >= {required} but we found version "
                f"{sqlite3.sqlite_version}"
            )

        kwargs = {}

        loop = get_running_loop()

        cache_key = (
            loop,
            self.connection_url,
            self.echo,
            self.timeout,
        )
        if cache_key not in ENGINES:
            # apply database timeout
            if self.timeout is not None:
                kwargs["connect_args"] = dict(timeout=self.timeout)

            # use `named` paramstyle for sqlite instead of `qmark` in very rare
            # circumstances, we've seen aiosqlite pass parameters in the wrong
            # order; by using named parameters we avoid this issue
            # see https://github.com/PrefectHQ/prefect/pull/6702
            kwargs["paramstyle"] = "named"

            # ensure a long-lasting pool is used with in-memory databases
            # because they disappear when the last connection closes
            if ":memory:" in self.connection_url:
                kwargs.update(
                    poolclass=sa.pool.AsyncAdaptedQueuePool,
                    pool_size=1,
                    max_overflow=0,
                    pool_recycle=-1,
                )

            engine = create_async_engine(self.connection_url, echo=self.echo, **kwargs)
            sa.event.listen(engine.sync_engine, "connect", self.setup_sqlite)
            sa.event.listen(engine.sync_engine, "begin", self.begin_sqlite_stmt)

            if TRACKER.active:
                TRACKER.track_pool(engine.pool)

            ENGINES[cache_key] = engine
            await self.schedule_engine_disposal(cache_key)
        return ENGINES[cache_key]

    async def schedule_engine_disposal(self, cache_key):
        """
        Dispose of an engine once the event loop is closing.

        See caveats at `add_event_loop_shutdown_callback`.

        We attempted to lazily clean up old engines when new engines are created, but
        if the loop the engine is attached to is already closed then the connections
        cannot be cleaned up properly and warnings are displayed.

        Engine disposal should only be important when running the application
        ephemerally. Notably, this is an issue in our tests where many short-lived event
        loops and engines are created which can consume all of the available database
        connection slots. Users operating at a scale where connection limits are
        encountered should be encouraged to use a standalone server.
        """

        async def dispose_engine(cache_key):
            engine = ENGINES.pop(cache_key, None)
            if engine:
                await engine.dispose()

        await add_event_loop_shutdown_callback(partial(dispose_engine, cache_key))

    def setup_sqlite(self, conn, record):
        """Issue PRAGMA statements to SQLITE on connect. PRAGMAs only last for the
        duration of the connection. See https://www.sqlite.org/pragma.html for more info.
        """
        # workaround sqlite transaction behavior
        self.begin_sqlite_conn(conn, record)

        cursor = conn.cursor()

        # write to a write-ahead-log instead and regularly commit the changes
        # this allows multiple concurrent readers even during a write transaction
        # even with the WAL we can get busy errors if we have transactions that:
        #  - t1 reads from a database
        #  - t2 inserts to the database
        #  - t1 tries to insert to the database
        # this can be resolved by using the IMMEDIATE transaction mode in t1
        cursor.execute("PRAGMA journal_mode = WAL;")

        # enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")

        # disable legacy alter table behavior as it will cause problems during
        # migrations when tables are renamed as references would otherwise be retained
        # in some locations
        # https://www.sqlite.org/pragma.html#pragma_legacy_alter_table
        cursor.execute("PRAGMA legacy_alter_table=OFF")

        # when using the WAL, we do need to sync changes on every write. sqlite
        # recommends using 'normal' mode which is much faster
        cursor.execute("PRAGMA synchronous = NORMAL;")

        # a higher cache size (default of 2000) for more aggressive performance
        cursor.execute("PRAGMA cache_size = 20000;")

        # wait for this amount of time while a table is locked
        # before returning and raising an error
        # setting the value very high allows for more 'concurrency'
        # without running into errors, but may result in slow api calls
        if PREFECT_TESTING_UNIT_TEST_MODE.value() is True:
            cursor.execute("PRAGMA busy_timeout = 5000;")  # 5s
        else:
            cursor.execute("PRAGMA busy_timeout = 60000;")  # 60s

        # `PRAGMA temp_store = memory;` moves temporary tables from disk into RAM
        # this supposedly speeds up reads, but it seems to actually
        # decrease overall performance, see https://github.com/PrefectHQ/prefect/pull/14812
        # cursor.execute("PRAGMA temp_store = memory;")

        cursor.close()

    def begin_sqlite_conn(self, conn, record):
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        # requires `begin_sqlite_stmt`
        # see https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
        conn.isolation_level = None

    def begin_sqlite_stmt(self, conn):
        # emit our own BEGIN
        # requires `begin_sqlite_conn`
        # see https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
        mode = SQLITE_BEGIN_MODE.get()
        if mode is not None:
            conn.exec_driver_sql(f"BEGIN {mode}")

        # Note this is intentionally a no-op if there is no BEGIN MODE set
        # This allows us to use SQLite's default behavior for reads which do not need
        # to be wrapped in a long-running transaction

    @asynccontextmanager
    async def begin_transaction(
        self, session: AsyncSession, with_for_update: bool = False
    ):
        token = SQLITE_BEGIN_MODE.set("IMMEDIATE" if with_for_update else "DEFERRED")

        try:
            async with session.begin() as transaction:
                yield transaction
        finally:
            SQLITE_BEGIN_MODE.reset(token)

    async def session(self, engine: AsyncEngine) -> AsyncSession:
        """
        Retrieves a SQLAlchemy session for an engine.

        Args:
            engine: a sqlalchemy engine
        """
        return AsyncSession(engine, expire_on_commit=False)

    async def create_db(self, connection, base_metadata):
        """Create the database"""

        await connection.run_sync(base_metadata.create_all)

    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

        await connection.run_sync(base_metadata.drop_all)

    def is_inmemory(self):
        """Returns true if database is run in memory"""

        return ":memory:" in self.connection_url or "mode=memory" in self.connection_url
