import sqlalchemy as sa
import sqlite3
import os
from asyncio import current_task, get_event_loop
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
)

from typing import Hashable, Tuple, Dict, AsyncGenerator
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import create_async_engine

from prefect import settings


class BaseDatabaseConfiguration(ABC):
    """
    Abstract base class used to inject database connection configuration into Orion.

    This configuration is responsible for defining how Orion creates and manages
    database connections and sessions.
    """

    def __init__(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
    ):
        self.connection_url = (
            connection_url or settings.orion.database.connection_url.get_secret_value()
        )
        self.echo = echo or settings.orion.database.echo
        self.timeout = timeout

    def _unique_key(self) -> Tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, self.connection_url)

    @abstractmethod
    async def engine(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
    ) -> sa.engine.Engine:
        """Returns a SqlAlchemy engine"""

    @abstractmethod
    async def session_factory(self, bind):
        """
        Retrieves a SQLAlchemy session factory for self.engine.
        The session factory is cached for each event loop.
        """

    @abstractmethod
    async def create_db(self, connection, base_metadata):
        """Create the database"""

    @abstractmethod
    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

    @abstractmethod
    def is_inmemory(self, engine):
        """Returns true if database is run in memory"""


class AsyncPostgresConfiguration(BaseDatabaseConfiguration):

    ENGINES = dict()
    ENGINE_DISPOSAL_REFS: Dict[tuple, AsyncGenerator] = dict()
    SESSION_FACTORIES = dict()

    async def engine(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
    ) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to self.connection_url
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to self.echo
            timeout (float, optional): The database statement timeout, in seconds.
                Defaults to self.timeout

        Returns:
            sa.engine.Engine: a SQLAlchemy engine
        """
        connection_url = connection_url or self.connection_url
        echo = echo or self.echo
        timeout = timeout or self.timeout

        loop = get_event_loop()

        cache_key = (
            loop,
            connection_url,
            echo,
            timeout,
        )
        if cache_key not in self.ENGINES:

            # apply database timeout
            kwargs = dict()
            if self.timeout is not None:
                kwargs["connect_args"] = dict(command_timeout=self.timeout)

            engine = create_async_engine(self.connection_url, echo=self.echo, **kwargs)

            self.ENGINES[cache_key] = engine
            await self.schedule_engine_disposal(cache_key)
        return self.ENGINES[cache_key]

    async def schedule_engine_disposal(self, cache_key):
        """
        Dispose of an engine once the event loop is closing.

        Requires use of `asyncio.run()` which waits for async generator shutdown by
        default or explicit call of `asyncio.shutdown_asyncgens()`. If the application
        is entered with `asyncio.run_until_complete()` and the user calls
        `asyncio.close()` without the generator shutdown call, this will not dispose the
        engine. As an alternative to suggesting users call `shutdown_asyncgens`
        (which can interfere with other async generators), `dispose_all_engines` is
        provided as a cleanup method.

        asyncio does not provided _any_ other way to clean up a resource when the event
        loop is about to close. We attempted to lazily clean up old engines when new
        engines are created, but if the loop the engine is attached to is already closed
        then the connections cannot be cleaned up properly and warnings are displayed.

        Engine disposal should only be important when running the application
        ephemerally. Notably, this is an issue in our tests where many short-lived event
        loops and engines are created which can consume all of the available database
        connection slots. Users operating at a scale where connection limits are
        encountered should be encouraged to use a standalone server.
        """

        async def dispose_engine(cache_key):
            try:
                yield
            except GeneratorExit:
                engine = self.ENGINES.pop(cache_key, None)
                if engine:
                    await engine.dispose()

                # Drop this iterator from the disposal just to keep things clean
                self.ENGINE_DISPOSAL_REFS.pop(cache_key, None)

        # Create the iterator and store it in a global variable so it is not cleaned up
        # when this function scope ends
        self.ENGINE_DISPOSAL_REFS[cache_key] = dispose_engine(cache_key).__aiter__()

        # Begin iterating so it will be cleaned up as an incomplete generator
        await self.ENGINE_DISPOSAL_REFS[cache_key].__anext__()

    async def session_factory(self, bind):
        """
        Retrieves a SQLAlchemy session factory for self.engine.
        The session factory is cached for each event loop.
        """
        loop = get_event_loop()
        cache_key = (loop, bind)
        if cache_key not in self.SESSION_FACTORIES:

            session_factory = sessionmaker(
                bind,
                future=True,
                expire_on_commit=False,
                class_=AsyncSession,
            )

            session = async_scoped_session(session_factory, scopefunc=current_task)
            self.SESSION_FACTORIES[cache_key] = session

        return self.SESSION_FACTORIES[cache_key]

    async def create_db(self, connection, base_metadata):
        """Create the database"""

        await connection.run_sync(base_metadata.create_all)

    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

        await connection.run_sync(base_metadata.drop_all)

    def is_inmemory(self, engine):
        """Returns true if database is run in memory"""

        return False


class AioSqliteConfiguration(BaseDatabaseConfiguration):

    SESSION_FACTORIES = dict()
    MIN_SQLITE_VERSION = (3, 24, 0)

    async def engine(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
    ) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to self.connection_url
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to self.echo
            timeout (float, optional): The database statement timeout, in seconds.
                Defaults to self.timeout

        Returns:
            sa.engine.Engine: a SQLAlchemy engine
        """
        connection_url = connection_url or self.connection_url
        echo = echo or self.echo
        timeout = timeout or self.timeout
        kwargs = {}

        # apply database timeout
        if timeout is not None:
            kwargs["connect_args"] = dict(timeout=timeout)

        # ensure a long-lasting pool is used with in-memory databases
        # because they disappear when the last connection closes
        if ":memory:" in connection_url:
            kwargs.update(poolclass=sa.pool.SingletonThreadPool)

        engine = create_async_engine(connection_url, echo=echo, **kwargs)
        sa.event.listen(engine.sync_engine, "engine_connect", self.setup_sqlite)

        if sqlite3.sqlite_version_info < self.MIN_SQLITE_VERSION:
            required = ".".join(str(v) for v in self.MIN_SQLITE_VERSION)
            raise RuntimeError(
                f"Orion requires sqlite >= {required} but we found version "
                f"{sqlite3.sqlite_version}"
            )

        return engine

    def setup_sqlite(self, conn, named=True):
        """Issue PRAGMA statements to SQLITE on connect. PRAGMAs only last for the
        duration of the connection. See https://www.sqlite.org/pragma.html for more info."""
        # enable foreign keys
        conn.execute(sa.text("PRAGMA foreign_keys = ON;"))

        # write to a write-ahead-log instead and regularly
        # commit the changes
        # this allows multiple concurrent readers even during
        # a write transaction
        conn.execute(sa.text("PRAGMA journal_mode = WAL;"))

        # wait for this amount of time while a table is locked
        # before returning and rasing an error
        # setting the value very high allows for more 'concurrency'
        # without running into errors, but may result in slow api calls
        conn.execute(sa.text("PRAGMA busy_timeout = 60000;"))  # 60s
        conn.commit()

    async def session_factory(self, bind):
        """
        Retrieves a SQLAlchemy session factory for self.engine.
        The session factory is cached for each event loop.
        """
        loop = get_event_loop()
        cache_key = (loop, bind)
        if cache_key not in self.SESSION_FACTORIES:

            session_factory = sessionmaker(
                bind,
                future=True,
                expire_on_commit=False,
                class_=AsyncSession,
            )

            session = async_scoped_session(session_factory, scopefunc=current_task)
            self.SESSION_FACTORIES[cache_key] = session

        return self.SESSION_FACTORIES[cache_key]

    async def create_db(self, connection, base_metadata):
        """Create the database"""

        await connection.run_sync(base_metadata.create_all)

    async def drop_db(self, connection, base_metadata):
        """Drop the database"""

        await connection.run_sync(base_metadata.drop_all)

    def is_inmemory(self, engine):
        """Returns true if database is run in memory"""

        return (
            ":memory:" in engine.url.database
            or "mode=memory" in engine.url.database
            or not os.path.exists(engine.url.database)
        )
