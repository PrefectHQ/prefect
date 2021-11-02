import datetime
import os
import pendulum
import sqlalchemy as sa
import sqlite3

from abc import ABC, abstractmethod, abstractproperty
from asyncio import current_task, get_event_loop
from sqlalchemy.orm import as_declarative, sessionmaker
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    create_async_engine,
)
from typing import List, Dict, AsyncGenerator
from prefect import settings
from prefect.orion.database.mixins import (
    BaseMixin,
    FlowMixin,
    FlowRunMixin,
    FlowRunStateMixin,
    TaskRunMixin,
    TaskRunStateMixin,
    TaskRunStateCacheMixin,
    DeploymentMixin,
    SavedSearchMixin,
)


async def create_db(engine=None):  # TODO - should go somewhere else
    """Create all database tables."""
    from prefect.orion.database.dependencies import provide_database_interface

    db_config = await provide_database_interface()
    if engine is None:
        engine = await db_config.engine()

    async with engine.begin() as conn:
        await conn.run_sync(db_config.Base.metadata.create_all)


async def drop_db(engine=None):
    """Drop all database tables."""

    from prefect.orion.database.dependencies import provide_database_interface

    db_config = await provide_database_interface()
    if engine is None:
        engine = await db_config.engine()
    async with engine.begin() as conn:
        await conn.run_sync(db_config.Base.metadata.drop_all)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class OrionDBInterface(metaclass=Singleton):

    # define naming conventions for our Base class to use
    # sqlalchemy will use the following templated strings
    # to generate the names of indices, constraints, and keys
    #
    # we offset the table name with two underscores (__) to
    # help differentiate, for example, between "flow_run.state_type"
    # and "flow_run_state.type".
    #
    # more information on this templating and available
    # customization can be found here
    # https://docs.sqlalchemy.org/en/14/core/metadata.html#sqlalchemy.schema.MetaData
    #
    # this also allows us to avoid having to specify names explicitly
    # when using sa.ForeignKey.use_alter = True
    # https://docs.sqlalchemy.org/en/14/core/constraints.html

    ENGINES = dict()
    SESSION_FACTORIES = dict()
    ENGINE_DISPOSAL_QUEUE: Dict[tuple, AsyncGenerator] = dict()

    def __init__(
        self,
        db_config=None,
        base_model_mixins: List = [],
    ):
        self.connection_url = settings.orion.database.connection_url.get_secret_value
        self.echo = settings.orion.database.echo
        self.timeout = None

        self.base_metadata = sa.schema.MetaData(
            naming_convention={
                "ix": "ix_%(table_name)s__%(column_0_N_name)s",
                "uq": "uq_%(table_name)s__%(column_0_N_name)s",
                "ck": "ck_%(table_name)s__%(constraint_name)s",
                "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
                "pk": "pk_%(table_name)s",
            }
        )

        self.config = db_config
        self.Base = self.create_base_model()
        self.create_orm_models()
        self.run_migrations()

    def create_base_model(self):
        @as_declarative(metadata=self.base_metadata)
        class Base(*self.config.base_model_mixins, BaseMixin):
            pass

        return Base

    def create_orm_models(self):
        class Flow(FlowMixin, self.Base):
            pass

        class FlowRunState(FlowRunStateMixin, self.Base):
            pass

        class TaskRunState(TaskRunStateMixin, self.Base):
            pass

        class TaskRunStateCache(TaskRunStateCacheMixin, self.Base):
            pass

        class FlowRun(FlowRunMixin, self.Base):
            pass

        class TaskRun(TaskRunMixin, self.Base):
            pass

        class Deployment(DeploymentMixin, self.Base):
            pass

        class SavedSearch(SavedSearchMixin, self.Base):
            pass

        # TODO - move these to proper migrations
        sa.Index(
            "uq_flow_run_state__flow_run_id_timestamp_desc",
            "flow_run_id",
            FlowRunState.timestamp.desc(),
            unique=True,
        )

        sa.Index(
            "uq_task_run_state__task_run_id_timestamp_desc",
            TaskRunState.task_run_id,
            TaskRunState.timestamp.desc(),
            unique=True,
        )

        sa.Index(
            "ix_task_run_state_cache__cache_key_created_desc",
            TaskRunStateCache.cache_key,
            sa.desc("created"),
        )

        sa.Index(
            "uq_flow_run__flow_id_idempotency_key",
            FlowRun.flow_id,
            FlowRun.idempotency_key,
            unique=True,
        )

        sa.Index(
            "ix_flow_run__expected_start_time_desc",
            FlowRun.expected_start_time.desc(),
        )
        sa.Index(
            "ix_flow_run__next_scheduled_start_time_asc",
            FlowRun.next_scheduled_start_time.asc(),
        )
        sa.Index(
            "ix_flow_run__end_time_desc",
            FlowRun.end_time.desc(),
        )
        sa.Index(
            "ix_flow_run__start_time",
            FlowRun.start_time,
        )
        sa.Index(
            "ix_flow_run__state_type",
            FlowRun.state_type,
        )

        sa.Index(
            "uq_task_run__flow_run_id_task_key_dynamic_key",
            TaskRun.flow_run_id,
            TaskRun.task_key,
            TaskRun.dynamic_key,
            unique=True,
        )

        sa.Index(
            "ix_task_run__expected_start_time_desc",
            TaskRun.expected_start_time.desc(),
        )
        sa.Index(
            "ix_task_run__next_scheduled_start_time_asc",
            TaskRun.next_scheduled_start_time.asc(),
        )
        sa.Index(
            "ix_task_run__end_time_desc",
            TaskRun.end_time.desc(),
        )
        sa.Index(
            "ix_task_run__start_time",
            TaskRun.start_time,
        )
        sa.Index(
            "ix_task_run__state_type",
            TaskRun.state_type,
        )

        sa.Index(
            "uq_deployment__flow_id_name",
            Deployment.flow_id,
            Deployment.name,
            unique=True,
        )

        self.Flow = Flow
        self.FlowRunState = FlowRunState
        self.TaskRunState = TaskRunState
        self.TaskRunStateCache = TaskRunStateCache
        self.FlowRun = FlowRun
        self.TaskRun = TaskRun
        self.Deployment = Deployment
        self.SavedSearch = SavedSearch

    def run_migrations(self):
        """Run database migrations"""
        self.config.run_migrations(self.Base)

    async def insert(self, model):
        """Returns an INSERT statement specific to a dialect"""
        return (self.config.insert)(model)

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return [self.Deployment.flow_id, self.Deployment.name]

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return [self.FlowRun.flow_id, self.FlowRun.idempotency_key]

    @property
    def flow_unique_upsert_columns(self):
        """Unique columns for upserting a Flow"""
        return [self.Flow.name]

    @property
    def saved_search_unique_upsert_columns(self):
        """Unique columns for upserting a SavedSearch"""
        return [self.SavedSearch.name]

    @property
    def task_run_unique_upsert_columns(self):
        """Unique columns for upserting a TaskRun"""
        return [
            self.TaskRun.flow_run_id,
            self.TaskRun.task_key,
            self.TaskRun.dynamic_key,
        ]

    def set_state_id_on_inserted_flow_runs_statement(
        self, inserted_flow_run_ids, insert_flow_run_states
    ):
        """Given a list of flow run ids and associated states, set the state_id
        to the appropriate state for all flow runs"""
        return self.config.set_state_id_on_inserted_flow_runs_statement(
            self.FlowRun,
            self.FlowRunState,
            inserted_flow_run_ids,
            insert_flow_run_states,
        )

    async def engine(self, connection_url=None):
        loop = get_event_loop()
        connection_url = connection_url or self.connection_url()

        cache_key = (loop, connection_url, self.echo, self.timeout)
        if cache_key not in self.ENGINES:

            engine = await self.config.engine(
                connection_url,
                self.echo,
                self.timeout,
            )

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
                self.ENGINE_DISPOSAL_QUEUE.pop(cache_key)

        # Create the iterator and store it in a global variable so it is not cleaned up
        # when this function scope ends
        self.ENGINE_DISPOSAL_QUEUE[cache_key] = dispose_engine(cache_key).__aiter__()

        # Begin iterating so it will be cleaned up as an incomplete generator
        await self.ENGINE_DISPOSAL_QUEUE[cache_key].__anext__()

    async def clear_engine_cache(self):
        self.ENGINES.clear()

    async def session_factory(self):
        loop = get_event_loop()
        bind = await self.engine()
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

    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        return self.config.make_timestamp_intervals(start_time, end_time, interval)

    @property
    def uses_json_strings(self):
        return self.config.uses_json_strings

    def max(self, *values):
        return self.config.max(*values)

    def cast_to_json(self, json_obj):
        return self.config.cast_to_json(json_obj)

    def build_json_object(self, *args):
        return self.config.build_json_object(*args)

    def json_arr_agg(self, json_array):
        return self.config.json_arr_agg(json_array)


class DatabaseConfigurationBase(ABC):
    @abstractmethod
    def run_migrations():
        ...

    @abstractmethod
    async def engine():
        ...

    @abstractmethod
    def set_state_id_on_inserted_flow_runs_statement():
        ...

    @abstractproperty
    def insert():
        ...

    @abstractproperty
    def base_model_mixins():
        ...

    @abstractmethod
    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        ...

    @abstractproperty
    def uses_json_strings():
        ...

    @abstractmethod
    def max(self, *values):
        ...

    @abstractmethod
    def cast_to_json(self, json_obj):
        ...

    @abstractmethod
    def build_json_object():
        ...

    @abstractmethod
    def json_arr_agg():
        ...


class AsyncPostgresConfiguration(DatabaseConfigurationBase):
    # TODO - validate connection url for postgres and asyncpg driver

    @property
    def base_model_mixins(self):
        return []

    @property
    def insert(self):
        return postgresql.insert

    def run_migrations(self, base_model):
        """Run database migrations"""

        # in order to index or created generated columns from timestamps stored in JSON,
        # we need a custom IMMUTABLE function for casting to timestamp
        # (because timestamp is not actually immutable)
        sa.event.listen(
            base_model.metadata,
            "before_create",
            sa.DDL(
                """
                CREATE OR REPLACE FUNCTION text_to_timestamp_immutable(ts text)
                RETURNS timestamp with time zone
                AS
                $BODY$
                    select to_timestamp($1, 'YYYY-MM-DD"T"HH24:MI:SS"Z"');
                $BODY$
                LANGUAGE sql
                IMMUTABLE;
                """
            ),
        )

        sa.event.listen(
            base_model.metadata,
            "before_drop",
            sa.DDL(
                """
                DROP FUNCTION IF EXISTS text_to_timestamp_immutable;
                """
            ),
        )

    async def engine(
        self,
        connection_url,
        echo,
        timeout,
    ) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

        A new engine is created for each event loop and cached, so that engines are
        not shared across loops.

        If a sqlite in-memory database OR a non-existant sqlite file-based database
        is provided, it is automatically populated with database objects.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to the value in Prefect's settings.
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to the value in Prefect's settings.
            timeout (float, optional): The database statement timeout, in seconds

        Returns:
            sa.engine.Engine: a SQLAlchemy engine
        """
        kwargs = dict()

        # apply database timeout
        if timeout is not None:
            kwargs["connect_args"] = dict(command_timeout=timeout)

        return create_async_engine(connection_url, echo=echo, **kwargs)

    def set_state_id_on_inserted_flow_runs_statement(
        self, fr_model, frs_model, inserted_flow_run_ids, insert_flow_run_states
    ):
        """Given a list of flow run ids and associated states, set the state_id
        to the appropriate state for all flow runs"""
        # postgres supports `UPDATE ... FROM` syntax
        stmt = (
            sa.update(fr_model)
            .where(
                fr_model.id.in_(inserted_flow_run_ids),
                frs_model.flow_run_id == fr_model.id,
                frs_model.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .values(state_id=frs_model.id)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt

    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        # validate inputs
        start_time = pendulum.instance(start_time)
        end_time = pendulum.instance(end_time)
        assert isinstance(interval, datetime.timedelta)
        return (
            sa.select(
                sa.literal_column("dt").label("interval_start"),
                (sa.literal_column("dt") + interval).label("interval_end"),
            )
            .select_from(
                sa.func.generate_series(start_time, end_time, interval).alias("dt")
            )
            .where(sa.literal_column("dt") < end_time)
            # grab at most 500 intervals
            .limit(500)
        )

    @property
    def uses_json_strings(self):
        return False

    def max(self, *values):
        return sa.func.greatest

    def cast_to_json(self, json_obj):
        return json_obj

    def build_json_object(self, *args):
        return sa.func.jsonb_build_object(*args)

    def json_arr_agg(self, json_array):
        return sa.func.jsonb_agg(json_array)


class AioSqliteConfiguration(DatabaseConfigurationBase):
    # TODO - validate connection url for sqlite and driver
    MIN_SQLITE_VERSION = (3, 24, 0)

    def run_migrations(self, base_model):
        ...

    @property
    def base_model_mixins(self):
        return []

    @property
    def insert(self):
        return sqlite.insert

    async def engine(self, connection_url, echo, timeout) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

        A new engine is created for each event loop and cached, so that engines are
        not shared across loops.

        If a sqlite in-memory database OR a non-existant sqlite file-based database
        is provided, it is automatically populated with database objects.

        Args:
            connection_url (str, optional): The database connection string.
                Defaults to the value in Prefect's settings.
            echo (bool, optional): Whether to echo SQL sent
                to the database. Defaults to the value in Prefect's settings.
            timeout (float, optional): The database statement timeout, in seconds

        Returns:
            sa.engine.Engine: a SQLAlchemy engine
        """
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

        # if this is a new sqlite database create all database objects
        if (
            ":memory:" in engine.url.database
            or "mode=memory" in engine.url.database
            or not os.path.exists(engine.url.database)
        ):
            await create_db(engine=engine)

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

    def set_state_id_on_inserted_flow_runs_statement(
        self, fr_model, frs_model, inserted_flow_run_ids, insert_flow_run_states
    ):
        """Given a list of flow run ids and associated states, set the state_id
        to the appropriate state for all flow runs"""
        # sqlite requires a correlated subquery to update from another table
        subquery = (
            sa.select(frs_model.id)
            .where(
                frs_model.flow_run_id == fr_model.id,
                frs_model.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            sa.update(fr_model)
            .where(
                fr_model.id.in_(inserted_flow_run_ids),
            )
            .values(state_id=subquery)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt

    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        from prefect.orion.utilities.database import Timestamp

        # validate inputs
        start_time = pendulum.instance(start_time)
        end_time = pendulum.instance(end_time)
        assert isinstance(interval, datetime.timedelta)

        return (
            sa.text(
                r"""
                -- recursive CTE to mimic the behavior of `generate_series`,
                -- which is only available as a compiled extension
                WITH RECURSIVE intervals(interval_start, interval_end, counter) AS (
                    VALUES(
                        strftime('%Y-%m-%d %H:%M:%f000', :start_time),
                        strftime('%Y-%m-%d %H:%M:%f000', :start_time, :interval),
                        1
                        )

                    UNION ALL

                    SELECT interval_end, strftime('%Y-%m-%d %H:%M:%f000', interval_end, :interval), counter + 1
                    FROM intervals
                    -- subtract interval because recursive where clauses are effectively evaluated on a t-1 lag
                    WHERE
                        interval_start < strftime('%Y-%m-%d %H:%M:%f000', :end_time, :negative_interval)
                        -- don't compute more than 500 intervals
                        AND counter < 500
                )
                SELECT * FROM intervals
                """
            )
            .bindparams(
                start_time=str(start_time),
                end_time=str(end_time),
                interval=f"+{interval.total_seconds()} seconds",
                negative_interval=f"-{interval.total_seconds()} seconds",
            )
            .columns(interval_start=Timestamp(), interval_end=Timestamp())
        )

    @property
    def uses_json_strings(self):
        return True

    def max(self, *values):
        return sa.func.max(*values)

    def cast_to_json(self, json_obj):
        return sa.func.json(json_obj)

    def build_json_object(self, *args):
        return sa.func.json_object(*args)

    def json_arr_agg(self, json_array):
        return sa.func.json_group_array(json_array)
