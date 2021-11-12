import os
from typing import List
import sqlalchemy as sa
import sqlite3

from typing import Hashable, Tuple
from abc import ABC, abstractmethod, abstractproperty
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import as_declarative

from prefect import settings
from prefect.orion.database.orm_models import (
    ORMBase,
    ORMFlow,
    ORMFlowRun,
    ORMFlowRunState,
    ORMTaskRun,
    ORMTaskRunState,
    ORMTaskRunStateCache,
    ORMDeployment,
    ORMSavedSearch,
)


class DatabaseConfigurationBase(ABC):
    """
    Abstract base class used to inject database-specific configuration into Orion.
    """

    def __init__(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
        base_metadata: sa.schema.MetaData = None,
        base_model_mixins: List = None,
    ):
        self.connection_url = (
            connection_url or settings.orion.database.connection_url.get_secret_value()
        )
        self.echo = echo or settings.orion.database.echo
        self.timeout = timeout

        self.base_metadata = base_metadata or sa.schema.MetaData(
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
            naming_convention={
                "ix": "ix_%(table_name)s__%(column_0_N_name)s",
                "uq": "uq_%(table_name)s__%(column_0_N_name)s",
                "ck": "ck_%(table_name)s__%(constraint_name)s",
                "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
                "pk": "pk_%(table_name)s",
            }
        )
        self.base_model_mixins = base_model_mixins or []

        self._create_base_model()
        self._create_orm_models()

    def _create_base_model(self):
        """
        Defines the base ORM model and binds it to `self`. The base model will be
        extended by mixins specified in the database configuration. This method only
        runs on instantiation.
        """

        @as_declarative(metadata=self.base_metadata)
        class Base(*self.base_model_mixins, ORMBase):
            pass

        self.Base = Base

    def _create_orm_models(self):
        """
        Defines the ORM models used in Orion and binds them to the `self`. This method
        only runs on instantiation.
        """

        class Flow(ORMFlow, self.Base):
            pass

        class FlowRunState(ORMFlowRunState, self.Base):
            pass

        class TaskRunState(ORMTaskRunState, self.Base):
            pass

        class TaskRunStateCache(ORMTaskRunStateCache, self.Base):
            pass

        class FlowRun(ORMFlowRun, self.Base):
            pass

        class TaskRun(ORMTaskRun, self.Base):
            pass

        class Deployment(ORMDeployment, self.Base):
            pass

        class SavedSearch(ORMSavedSearch, self.Base):
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

    def _unique_key(self) -> Tuple[Hashable]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, self.connection_url)

    @abstractmethod
    def run_migrations(self, base_model):
        """Database-specific migration configuration"""

    @abstractmethod
    async def engine(
        self,
    ) -> sa.engine.Engine:
        """Returns a SqlAlchemy engine"""

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


class AsyncPostgresConfiguration(DatabaseConfigurationBase):
    # TODO - validate connection url for postgres and asyncpg driver

    def run_migrations(self, base_model):
        ...

    async def engine(
        self,
    ) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

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
        if self.timeout is not None:
            kwargs["connect_args"] = dict(command_timeout=self.timeout)

        return create_async_engine(self.connection_url, echo=self.echo, **kwargs)


class AioSqliteConfiguration(DatabaseConfigurationBase):
    # TODO - validate connection url for sqlite and driver

    MIN_SQLITE_VERSION = (3, 24, 0)

    def run_migrations(self, base_model):
        ...

    async def engine(
        self,
    ) -> sa.engine.Engine:
        """Retrieves an async SQLAlchemy engine.

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
        if self.timeout is not None:
            kwargs["connect_args"] = dict(timeout=self.timeout)

        # ensure a long-lasting pool is used with in-memory databases
        # because they disappear when the last connection closes
        if ":memory:" in self.connection_url:
            kwargs.update(poolclass=sa.pool.SingletonThreadPool)

        engine = create_async_engine(self.connection_url, echo=self.echo, **kwargs)
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
            async with engine.begin() as conn:
                await conn.run_sync(self.Base.metadata.create_all)

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
