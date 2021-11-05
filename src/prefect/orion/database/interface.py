import datetime
import sqlalchemy as sa

from asyncio import current_task, get_event_loop
from sqlalchemy.orm import as_declarative, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
)
from typing import List, Dict, AsyncGenerator
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
        query_components=None,
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
        self.queries = query_components
        self.Base = self.create_base_model()
        self.create_orm_models()
        self.run_migrations()

    def create_base_model(self):
        @as_declarative(metadata=self.base_metadata)
        class Base(*self.config.base_model_mixins, ORMBase):
            pass

        return Base

    def create_orm_models(self):
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

    async def create_db(self):
        engine = await self.engine()

        async with engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.create_all)

    async def drop_db(self):
        engine = await self.engine()

        async with engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.drop_all)

    def run_migrations(self):
        """Run database migrations"""
        self.config.run_migrations(self.Base)

    async def insert(self, model):
        """Returns an INSERT statement specific to a dialect"""
        return (self.queries.insert)(model)

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
        return self.queries.set_state_id_on_inserted_flow_runs_statement(
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
                self.Base.metadata,
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
                self.ENGINE_DISPOSAL_QUEUE.pop(cache_key, None)

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
        return self.queries.make_timestamp_intervals(start_time, end_time, interval)

    @property
    def uses_json_strings(self):
        return self.queries.uses_json_strings

    def max(self, *values):
        return self.queries.max(*values)

    def cast_to_json(self, json_obj):
        return self.queries.cast_to_json(json_obj)

    def build_json_object(self, *args):
        return self.queries.build_json_object(*args)

    def json_arr_agg(self, json_array):
        return self.queries.json_arr_agg(json_array)
