import datetime
import os

from prefect.orion.database.configurations import BaseDatabaseConfiguration
from prefect.orion.database.query_components import BaseQueryComponents
from prefect.orion.database.orm_models import BaseORMConfiguration


class DBSingleton(type):
    """Ensures that only one OrionDBInterface is created per unique key"""

    _instances = dict()

    def __call__(cls, *args, **kwargs):
        unique_key = (
            kwargs["database_config"]._unique_key(),
            kwargs["query_components"]._unique_key(),
            kwargs["orm"]._unique_key(),
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

    def __init__(
        self,
        database_config: BaseDatabaseConfiguration = None,
        query_components: BaseQueryComponents = None,
        orm: BaseORMConfiguration = None,
    ):

        self.database_config = database_config
        self.queries = query_components
        self.orm = orm

    async def create_db(self):
        """Create the database"""

        engine = await self.database_config.engine()

        async with engine.begin() as conn:
            await self.database_config.create_db(conn, self.Base.metadata)

    async def drop_db(self):
        """Drop the database"""

        engine = await self.database_config.engine()

        async with engine.begin() as conn:
            await self.database_config.drop_db(conn, self.Base.metadata)

    def run_migrations(self):
        """Run database migrations"""
        self.orm.run_migrations()

    async def engine(
        self,
        connection_url: str = None,
        echo: bool = None,
        timeout: float = None,
    ):
        """
        Provides a SqlAlchemy engine against a specific database.
        """
        engine = await self.database_config.engine(
            connection_url=connection_url, echo=echo, timeout=timeout
        )

        if self.database_config.is_inmemory(engine):
            async with engine.begin() as conn:
                await self.database_config.create_db(conn, self.Base.metadata)

        return engine

    async def session_factory(self):
        engine = await self.engine()
        return await self.database_config.session_factory(engine)

    @property
    def Base(self):
        """Base class for orm models"""
        return self.orm.Base

    @property
    def Flow(self):
        """A flow orm model"""
        return self.orm.Flow

    @property
    def FlowRun(self):
        """A flow run orm model"""
        return self.orm.FlowRun

    @property
    def FlowRunState(self):
        """A flow run state orm model"""
        return self.orm.FlowRunState

    @property
    def TaskRun(self):
        """A task run orm model"""
        return self.orm.TaskRun

    @property
    def TaskRunState(self):
        """A task run state orm model"""
        return self.orm.TaskRunState

    @property
    def TaskRunStateCache(self):
        """A task run state cache orm model"""
        return self.orm.TaskRunStateCache

    @property
    def Deployment(self):
        """A deployment orm model"""
        return self.orm.Deployment

    @property
    def SavedSearch(self):
        """A saved search orm model"""
        return self.orm.SavedSearch

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return self.orm.deployment_unique_upsert_columns

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return self.orm.flow_run_unique_upsert_columns

    @property
    def flow_unique_upsert_columns(self):
        """Unique columns for upserting a Flow"""
        return self.orm.flow_unique_upsert_columns

    @property
    def saved_search_unique_upsert_columns(self):
        """Unique columns for upserting a SavedSearch"""
        return self.orm.saved_search_unique_upsert_columns

    @property
    def task_run_unique_upsert_columns(self):
        """Unique columns for upserting a TaskRun"""
        return self.orm.task_run_unique_upsert_columns

    async def insert(self, model):
        """INSERTs a model into the database"""
        return self.queries.insert(model)

    def greatest(self, *values):
        return self.queries.greatest(*values)

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
