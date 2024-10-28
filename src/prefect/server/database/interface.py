import datetime
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from prefect.server.database import orm_models
from prefect.server.database.alembic_commands import alembic_downgrade, alembic_upgrade
from prefect.server.database.configurations import BaseDatabaseConfiguration
from prefect.server.database.query_components import BaseQueryComponents
from prefect.server.utilities.database import get_dialect
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class DBSingleton(type):
    """Ensures that only one database interface is created per unique key"""

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


class PrefectDBInterface(metaclass=DBSingleton):
    """
    An interface for backend-specific SqlAlchemy actions and ORM models.

    The REST API can be configured to run against different databases in order maintain
    performance at different scales. This interface integrates database- and dialect-
    specific configuration into a unified interface that the orchestration engine runs
    against.
    """

    def __init__(
        self,
        database_config: BaseDatabaseConfiguration,
        query_components: BaseQueryComponents,
        orm: orm_models.BaseORMConfiguration,
    ):
        self.database_config = database_config
        self.queries = query_components
        self.orm = orm

    async def create_db(self):
        """Create the database"""
        await self.run_migrations_upgrade()

    async def drop_db(self):
        """Drop the database"""
        await self.run_migrations_downgrade(revision="base")

    async def run_migrations_upgrade(self):
        """Run all upgrade migrations"""
        await run_sync_in_worker_thread(alembic_upgrade)

    async def run_migrations_downgrade(self, revision: str = "-1"):
        """Run all downgrade migrations"""
        await run_sync_in_worker_thread(alembic_downgrade, revision=revision)

    async def is_db_connectable(self):
        """
        Returns boolean indicating if the database is connectable.
        This method is used to determine if the server is ready to accept requests.
        """
        engine = await self.engine()
        try:
            async with engine.connect():
                return True
        except Exception:
            return False

    async def engine(self) -> AsyncEngine:
        """
        Provides a SqlAlchemy engine against a specific database.
        """
        engine = await self.database_config.engine()

        return engine

    async def session(self):
        """
        Provides a SQLAlchemy session.
        """
        engine = await self.engine()
        return await self.database_config.session(engine)

    @asynccontextmanager
    async def session_context(
        self, begin_transaction: bool = False, with_for_update: bool = False
    ):
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
                async with self.database_config.begin_transaction(
                    session, with_for_update=with_for_update
                ):
                    yield session
            else:
                yield session

    @property
    def dialect(self) -> sa.engine.Dialect:
        return get_dialect(self.database_config.connection_url)

    @property
    def Base(self):
        """Base class for orm models"""
        return orm_models.Base

    @property
    def Flow(self):
        """A flow orm model"""
        return orm_models.Flow

    @property
    def FlowRun(self):
        """A flow run orm model"""
        return orm_models.FlowRun

    @property
    def FlowRunState(self):
        """A flow run state orm model"""
        return orm_models.FlowRunState

    @property
    def TaskRun(self):
        """A task run orm model"""
        return orm_models.TaskRun

    @property
    def TaskRunState(self):
        """A task run state orm model"""
        return orm_models.TaskRunState

    @property
    def Artifact(self):
        """An artifact orm model"""
        return orm_models.Artifact

    @property
    def ArtifactCollection(self):
        """An artifact collection orm model"""
        return orm_models.ArtifactCollection

    @property
    def TaskRunStateCache(self):
        """A task run state cache orm model"""
        return orm_models.TaskRunStateCache

    @property
    def Deployment(self):
        """A deployment orm model"""
        return orm_models.Deployment

    @property
    def DeploymentSchedule(self):
        """A deployment schedule orm model"""
        return orm_models.DeploymentSchedule

    @property
    def SavedSearch(self):
        """A saved search orm model"""
        return orm_models.SavedSearch

    @property
    def WorkPool(self):
        """A work pool orm model"""
        return orm_models.WorkPool

    @property
    def Worker(self):
        """A worker process orm model"""
        return orm_models.Worker

    @property
    def Log(self):
        """A log orm model"""
        return orm_models.Log

    @property
    def ConcurrencyLimit(self):
        """A concurrency model"""
        return orm_models.ConcurrencyLimit

    @property
    def ConcurrencyLimitV2(self):
        """A v2 concurrency model"""
        return orm_models.ConcurrencyLimitV2

    @property
    def CsrfToken(self):
        """A csrf token model"""
        return orm_models.CsrfToken

    @property
    def WorkQueue(self):
        """A work queue model"""
        return orm_models.WorkQueue

    @property
    def Agent(self):
        """An agent model"""
        return orm_models.Agent

    @property
    def BlockType(self):
        """A block type model"""
        return orm_models.BlockType

    @property
    def BlockSchema(self):
        """A block schema model"""
        return orm_models.BlockSchema

    @property
    def BlockSchemaReference(self):
        """A block schema reference model"""
        return orm_models.BlockSchemaReference

    @property
    def BlockDocument(self):
        """A block document model"""
        return orm_models.BlockDocument

    @property
    def BlockDocumentReference(self):
        """A block document reference model"""
        return orm_models.BlockDocumentReference

    @property
    def FlowRunNotificationPolicy(self):
        """A flow run notification policy model"""
        return orm_models.FlowRunNotificationPolicy

    @property
    def FlowRunNotificationQueue(self):
        """A flow run notification queue model"""
        return orm_models.FlowRunNotificationQueue

    @property
    def Configuration(self):
        """An configuration model"""
        return orm_models.Configuration

    @property
    def Variable(self):
        """A variable model"""
        return orm_models.Variable

    @property
    def FlowRunInput(self):
        """A flow run input model"""
        return orm_models.FlowRunInput

    @property
    def Automation(self):
        """An automation model"""
        return orm_models.Automation

    @property
    def AutomationBucket(self):
        """An automation bucket model"""
        return orm_models.AutomationBucket

    @property
    def AutomationRelatedResource(self):
        """An automation related resource model"""
        return orm_models.AutomationRelatedResource

    @property
    def CompositeTriggerChildFiring(self):
        """A model capturing a composite trigger's child firing"""
        return orm_models.CompositeTriggerChildFiring

    @property
    def AutomationEventFollower(self):
        """A model capturing one event following another event"""
        return orm_models.AutomationEventFollower

    @property
    def Event(self):
        """An event model"""
        return orm_models.Event

    @property
    def EventResource(self):
        """An event resource model"""
        return orm_models.EventResource

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
    def artifact_collection_unique_upsert_columns(self):
        """Unique columns for upserting an ArtifactCollection"""
        return self.orm.artifact_collection_unique_upsert_columns

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

    def insert(self, model):
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
            orm_models.FlowRun,
            orm_models.FlowRunState,
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
            session=session, limit=limit
        )

    async def read_configuration_value(self, session: AsyncSession, key: str):
        """Read a configuration value"""
        return await self.queries.read_configuration_value(session=session, key=key)

    def clear_configuration_value_cache_for_key(self, key: str):
        """Removes a configuration key from the cache."""
        return self.queries.clear_configuration_value_cache_for_key(key=key)
