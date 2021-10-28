import os
from typing import Any, List
import sqlalchemy as sa
from sqlalchemy.orm import as_declarative, sessionmaker
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    create_async_engine,
)
from pydantic import BaseModel, Field
from asyncio import current_task, get_event_loop


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

ENGINES = {}  # TODO - put this in the connection abstraction?
SESSION_FACTORIES = {}


async def create_db():  # TODO - should go somewhere else
    """Create all database tables."""
    from prefect.orion.database.dependencies import get_database_configuration

    db_config = await get_database_configuration()
    engine = await db_config.engine()
    async with engine.begin() as conn:
        await conn.run_sync(db_config.Base.metadata.create_all)


async def drop_db():
    """Drop all database tables."""
    from prefect.orion.database.dependencies import get_database_configuration

    db_config = await get_database_configuration()
    engine = await db_config.engine()
    async with engine.begin() as conn:
        await conn.run_sync(db_config.Base.metadata.drop_all)


class DatabaseConfigurationBaseModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    connection_url: str = Field(
        default_factory=settings.orion.database.connection_url.get_secret_value
    )
    echo: bool = settings.orion.database.echo
    timeout: float = None

    # TODO - typing
    base_model_mixins: List = []
    Base: Any = None
    Flow: Any = None
    FlowRun: Any = None
    FlowRunState: Any = None
    TaskRun: Any = None
    TaskRunState: Any = None
    TaskRunStateCache: Any = None
    Deployment: Any = None
    SavedSearch: Any = None

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
    base_metadata = sa.schema.MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s__%(column_0_N_name)s",
            "uq": "uq_%(table_name)s__%(column_0_N_name)s",
            "ck": "ck_%(table_name)s__%(constraint_name)s",
            "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.Base = self.create_base_model()
        self.create_orm_models()

    def create_base_model(self):
        @as_declarative(metadata=self.base_metadata)
        class Base(*self.base_model_mixins, BaseMixin):
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

    async def dialect_specific_insert(self, model):  # TODO - implement per config
        """Returns an INSERT statement specific to a dialect"""
        inserts = {
            "postgresql": postgresql.insert,
            "sqlite": sqlite.insert,
        }
        return inserts[(await self.engine()).url.get_dialect().name](model)

    def set_state_id_on_inserted_flow_runs_statement(
        self, inserted_flow_run_ids, insert_flow_run_states
    ):
        raise NotImplementedError()


class AsyncPostgresConfiguration(DatabaseConfigurationBaseModel):
    # TODO - validate connection url for postgres and asyncpg driver

    async def engine(
        self,
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

        loop = get_event_loop()
        cache_key = (loop, self.connection_url, self.echo, self.timeout)
        if cache_key not in ENGINES:
            kwargs = {}

            # apply database timeout
            if self.timeout is not None:
                kwargs["connect_args"] = dict(command_timeout=self.timeout)

            engine = create_async_engine(self.connection_url, echo=self.echo, **kwargs)

            ENGINES[cache_key] = engine
        return ENGINES[cache_key]

    async def session_factory(
        self,
    ) -> async_scoped_session:
        """Retrieves a SQLAlchemy session factory for the provided bind.
        The session factory is cached for each event loop.

        Args:
            engine (Union[sa.engine.Engine, sa.engine.Connection], optional): An
                async SQLAlchemy engine or connection. If none is
                provided, `get_engine()` is called to recover one.

        Returns:
            sa.ext.asyncio.scoping.async_scoped_session: an async scoped session factory
        """
        bind = await self.engine()

        loop = get_event_loop()
        cache_key = (loop, bind)
        if cache_key not in SESSION_FACTORIES:
            # create session factory
            session_factory = sessionmaker(
                bind,
                future=True,
                expire_on_commit=False,
                class_=AsyncSession,
            )

            # create session factory with async scoping
            SESSION_FACTORIES[cache_key] = async_scoped_session(
                session_factory, scopefunc=current_task
            )

        return SESSION_FACTORIES[cache_key]

    def set_state_id_on_inserted_flow_runs_statement(
        self, inserted_flow_run_ids, insert_flow_run_states
    ):
        # postgres supports `UPDATE ... FROM` syntax
        stmt = (
            sa.update(self.FlowRun)
            .where(
                self.FlowRun.id.in_(inserted_flow_run_ids),
                self.FlowRunState.flow_run_id == self.FlowRun.id,
                self.FlowRunState.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .values(state_id=self.FlowRunState.id)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt


class AioSqliteConfiguration(DatabaseConfigurationBaseModel):
    # TODO - validate connection url for sqlite and driver

    async def engine(self) -> sa.engine.Engine:
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

        loop = get_event_loop()
        cache_key = (loop, self.connection_url, self.echo, self.timeout)
        if cache_key not in ENGINES:
            kwargs = {}

            # apply database timeout
            if self.timeout is not None:
                kwargs["connect_args"] = dict(timeout=self.timeout)

            # ensure a long-lasting pool is used with in-memory databases
            # because they disappear when the last connection closes
            if ":memory:" in self.connection_url:
                kwargs.update(poolclass=sa.pool.SingletonThreadPool)

            engine = create_async_engine(self.connection_url, echo=self.echo, **kwargs)
            sa.event.listen(engine.sync_engine, "engine_connect", self.setup_sqlite)

            # if this is a new sqlite database create all database objects
            if (
                ":memory:" in engine.url.database
                or "mode=memory" in engine.url.database
                or not os.path.exists(engine.url.database)
            ):
                await create_db(engine)

            ENGINES[cache_key] = engine
        return ENGINES[cache_key]

    async def session_factory(
        self,
    ) -> async_scoped_session:
        """Retrieves a SQLAlchemy session factory for the provided bind.
        The session factory is cached for each event loop.

        Args:
            engine (Union[sa.engine.Engine, sa.engine.Connection], optional): An
                async SQLAlchemy engine or connection. If none is
                provided, `get_engine()` is called to recover one.

        Returns:
            sa.ext.asyncio.scoping.async_scoped_session: an async scoped session factory
        """
        bind = await self.engine()

        loop = get_event_loop()
        cache_key = (loop, bind)
        if cache_key not in SESSION_FACTORIES:
            # create session factory
            session_factory = sessionmaker(
                bind,
                future=True,
                expire_on_commit=False,
                class_=AsyncSession,
            )

            # create session factory with async scoping
            SESSION_FACTORIES[cache_key] = async_scoped_session(
                session_factory, scopefunc=current_task
            )

        return SESSION_FACTORIES[cache_key]

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
        self, inserted_flow_run_ids, insert_flow_run_states
    ):
        # sqlite requires a correlated subquery to update from another table
        subquery = (
            sa.select(self.FlowRunState.id)
            .where(
                self.FlowRunState.flow_run_id == self.FlowRun.id,
                self.FlowRunState.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            sa.update(self.FlowRun)
            .where(
                self.FlowRun.id.in_(inserted_flow_run_ids),
            )
            .values(state_id=subquery)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt
