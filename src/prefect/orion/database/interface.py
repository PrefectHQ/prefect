import datetime

from asyncio import current_task, get_event_loop
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
)
from typing import Dict, AsyncGenerator
from prefect.orion.database.configurations import DatabaseConfigurationBase
from prefect.orion.database.query_components import QueryComponentsBase


class DBSingleton(type):
    """Ensures that only one OrionDBInterface is created per unique key"""

    _instances = dict()

    def __call__(cls, *args, **kwargs):
        unique_key = (
            kwargs["db_config"]._unique_key(),
            kwargs["query_components"]._unique_key(),
        )
        if unique_key not in cls._instances:
            cls._instances[unique_key] = super(DBSingleton, cls).__call__(
                *args, **kwargs
            )
        return cls._instances[unique_key]


class OrionDBInterface(metaclass=DBSingleton):
    """
    An interface for backend-specific SqlAlchemy actions and ORM models.

    Orion can be configured to run against different databases in order maintain
    performance at different scales. This interface integrates database- and dialect-
    specific configuration into a unified interface that the orchestration engine runs
    against.
    """

    ENGINES = dict()
    SESSION_FACTORIES = dict()
    ENGINE_DISPOSAL_REFS: Dict[tuple, AsyncGenerator] = dict()

    def __init__(
        self,
        db_config: DatabaseConfigurationBase = None,
        query_components: QueryComponentsBase = None,
    ):

        self.config = db_config
        self.queries = query_components

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
        self.config.run_migrations()

    async def engine(self):
        """
        Provides a SqlAlchemy engine against a specific database.

        A new engine is created for each event loop and cached, so that engines are
        not shared across loops.
        """

        loop = get_event_loop()

        cache_key = (
            loop,
            self.config.connection_url,
            self.config.echo,
            self.config.timeout,
        )
        if cache_key not in self.ENGINES:

            engine = await self.config.engine()

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

    async def clear_engine_cache(self):
        self.ENGINES.clear()

    @property
    def Base(self):
        """Base class for orm models"""
        return self.config.Base

    @property
    def Flow(self):
        """A flow orm model"""
        return self.config.Flow

    @property
    def FlowRun(self):
        """A flow run orm model"""
        return self.config.FlowRun

    @property
    def FlowRunState(self):
        """A flow run state orm model"""
        return self.config.FlowRunState

    @property
    def TaskRun(self):
        """A task run orm model"""
        return self.config.TaskRun

    @property
    def TaskRunState(self):
        """A task run state orm model"""
        return self.config.TaskRunState

    @property
    def TaskRunStateCache(self):
        """A task run state cache orm model"""
        return self.config.TaskRunStateCache

    @property
    def Deployment(self):
        """A deployment orm model"""
        return self.config.Deployment

    @property
    def SavedSearch(self):
        """A saved search orm model"""
        return self.config.SavedSearch

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return self.config.deployment_unique_upsert_columns

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return self.config.flow_run_unique_upsert_columns

    @property
    def flow_unique_upsert_columns(self):
        """Unique columns for upserting a Flow"""
        return self.config.flow_unique_upsert_columns

    @property
    def saved_search_unique_upsert_columns(self):
        """Unique columns for upserting a SavedSearch"""
        return self.config.saved_search_unique_upsert_columns

    @property
    def task_run_unique_upsert_columns(self):
        """Unique columns for upserting a TaskRun"""
        return self.config.task_run_unique_upsert_columns

    async def insert(self, model):
        """INSERTs a model into the database"""
        return self.queries.insert(model)

    def max(self, *values):
        return self.queries.max(*values)

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

    @property
    def uses_json_strings(self):
        return self.queries.uses_json_strings

    def cast_to_json(self, json_obj):
        return self.queries.cast_to_json(json_obj)

    def build_json_object(self, *args):
        return self.queries.build_json_object(*args)

    def json_arr_agg(self, json_array):
        return self.queries.json_arr_agg(json_array)
