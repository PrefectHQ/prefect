import datetime
from contextlib import asynccontextmanager

import sqlalchemy as sa

from prefect.orion.database.alembic_commands import alembic_downgrade, alembic_upgrade
from prefect.orion.database.configurations import BaseDatabaseConfiguration
from prefect.orion.database.orm_models import BaseORMConfiguration
from prefect.orion.database.query_components import BaseQueryComponents
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class DBSingleton(type):
    """Ensures that only one OrionDBInterface is created per unique key"""

    _instances = dict()

    def __call__(cls, *args, **kwargs):
        unique_key = (
            cls.__name__,
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
        database_config: BaseDatabaseConfiguration,
        query_components: BaseQueryComponents,
        orm: BaseORMConfiguration,
    ):

        self.database_config = database_config
        self.queries = query_components
        self.orm = orm

    async def create_db(self):
        """Create the database"""
        await self.run_migrations_upgrade()

    async def drop_db(self):
        """Drop the database"""
        await self.run_migrations_downgrade()

    async def run_migrations_upgrade(self):
        """Run all upgrade migrations"""
        await run_sync_in_worker_thread(alembic_upgrade)

    async def run_migrations_downgrade(self):
        """Run all downgrade migrations"""
        await run_sync_in_worker_thread(alembic_downgrade)

    async def engine(self):
        """
        Provides a SqlAlchemy engine against a specific database.
        """
        engine = await self.database_config.engine()

        if self.database_config.is_inmemory():
            async with engine.begin() as conn:
                await self.database_config.create_db(conn, self.Base.metadata)

        return engine

    async def session(self):
        """
        Provides a SQLAlchemy session.
        """
        engine = await self.engine()
        return await self.database_config.session(engine)

    @asynccontextmanager
    async def session_context(self, begin_transaction: bool = False):
        """
        Provides a SQLAlchemy session and a context manager for opening/closing
        the underlying connection.

        Args:
            begin_transaction: if True, the context manager will begin a SQL transaction.
                Exiting the context manager will COMMIT or ROLLBACK any changes.
        """
        session = await self.session()
        async with session:
            if begin_transaction:
                async with session.begin():
                    yield session
            else:
                yield session

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
    def Log(self):
        """A log orm model"""
        return self.orm.Log

    @property
    def ConcurrencyLimit(self):
        """A concurrency model"""
        return self.orm.ConcurrencyLimit

    @property
    def WorkQueue(self):
        """A work queue model"""
        return self.orm.WorkQueue

    @property
    def Agent(self):
        """An agent model"""
        return self.orm.Agent

    @property
    def BlockType(self):
        """A block type model"""
        return self.orm.BlockType

    @property
    def BlockSchema(self):
        """A block schema model"""
        return self.orm.BlockSchema

    @property
    def BlockSchemaReference(self):
        """A block schema reference model"""
        return self.orm.BlockSchemaReference

    @property
    def BlockDocument(self):
        """A block document model"""
        return self.orm.BlockDocument

    @property
    def BlockDocumentReference(self):
        """A block document reference model"""
        return self.orm.BlockDocumentReference

    @property
    def FlowRunNotificationPolicy(self):
        """A flow run notification policy model"""
        return self.orm.FlowRunNotificationPolicy

    @property
    def FlowRunNotificationQueue(self):
        """A flow run notification queue model"""
        return self.orm.FlowRunNotificationQueue

    @property
    def Configuration(self):
        """An configuration model"""
        return self.orm.Configuration

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return self.orm.deployment_unique_upsert_columns

    @property
    def concurrency_limit_unique_upsert_columns(self):
        """Unique columns for upserting a ConcurrencyLimit"""
        return self.orm.concurrency_limit_unique_upsert_columns

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return self.orm.flow_run_unique_upsert_columns

    @property
    def block_type_unique_upsert_columns(self):
        """Unique columns for upserting a BlockType"""
        return self.orm.block_type_unique_upsert_columns

    @property
    def block_schema_unique_upsert_columns(self):
        """Unique columns for upserting a BlockSchema"""
        return self.orm.block_schema_unique_upsert_columns

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

    @property
    def block_document_unique_upsert_columns(self):
        """Unique columns for upserting a BlockDocument"""
        return self.orm.block_document_unique_upsert_columns

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

    async def get_flow_run_notifications_from_queue(
        self, session: sa.orm.Session, limit: int
    ):
        return await self.queries.get_flow_run_notifications_from_queue(
            session=session, db=self, limit=limit
        )
