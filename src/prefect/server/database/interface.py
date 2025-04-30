from collections.abc import Hashable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from typing_extensions import TypeAlias

from prefect.server.database import orm_models
from prefect.server.database.alembic_commands import alembic_downgrade, alembic_upgrade
from prefect.server.database.configurations import BaseDatabaseConfiguration
from prefect.server.utilities.database import get_dialect
from prefect.utilities.asyncutils import run_sync_in_worker_thread

if TYPE_CHECKING:
    from prefect.server.database.query_components import BaseQueryComponents

_UniqueKey: TypeAlias = tuple[Hashable, ...]


class DBSingleton(type):
    """Ensures that only one database interface is created per unique key"""

    _instances: dict[tuple[str, _UniqueKey, _UniqueKey, _UniqueKey], "DBSingleton"] = (
        dict()
    )

    def __call__(
        cls,
        *args: Any,
        database_config: BaseDatabaseConfiguration,
        query_components: "BaseQueryComponents",
        orm: orm_models.BaseORMConfiguration,
        **kwargs: Any,
    ) -> "DBSingleton":
        instance_key = (
            cls.__name__,
            database_config.unique_key(),
            query_components.unique_key(),
            orm.unique_key(),
        )
        try:
            instance = cls._instances[instance_key]
        except KeyError:
            instance = cls._instances[instance_key] = super().__call__(
                *args,
                database_config=database_config,
                query_components=query_components,
                orm=orm,
                **kwargs,
            )
        return instance


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
        query_components: "BaseQueryComponents",
        orm: orm_models.BaseORMConfiguration,
    ):
        self.database_config = database_config
        self.queries = query_components
        self.orm = orm

    async def create_db(self) -> None:
        """Create the database"""
        await self.run_migrations_upgrade()

    async def drop_db(self) -> None:
        """Drop the database"""
        await self.run_migrations_downgrade(revision="base")

    async def run_migrations_upgrade(self) -> None:
        """Run all upgrade migrations"""
        await run_sync_in_worker_thread(alembic_upgrade)

    async def run_migrations_downgrade(self, revision: str = "-1") -> None:
        """Run all downgrade migrations"""
        await run_sync_in_worker_thread(alembic_downgrade, revision=revision)

    async def is_db_connectable(self) -> bool:
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

    async def session(self) -> AsyncSession:
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
    def dialect(self) -> type[sa.engine.Dialect]:
        return get_dialect(self.database_config.connection_url)

    @property
    def Base(self) -> type[orm_models.Base]:
        """Base class for orm models"""
        return orm_models.Base

    @property
    def Flow(self) -> type[orm_models.Flow]:
        """A flow orm model"""
        return orm_models.Flow

    @property
    def FlowRun(self) -> type[orm_models.FlowRun]:
        """A flow run orm model"""
        return orm_models.FlowRun

    @property
    def FlowRunState(self) -> type[orm_models.FlowRunState]:
        """A flow run state orm model"""
        return orm_models.FlowRunState

    @property
    def TaskRun(self) -> type[orm_models.TaskRun]:
        """A task run orm model"""
        return orm_models.TaskRun

    @property
    def TaskRunState(self) -> type[orm_models.TaskRunState]:
        """A task run state orm model"""
        return orm_models.TaskRunState

    @property
    def Artifact(self) -> type[orm_models.Artifact]:
        """An artifact orm model"""
        return orm_models.Artifact

    @property
    def ArtifactCollection(self) -> type[orm_models.ArtifactCollection]:
        """An artifact collection orm model"""
        return orm_models.ArtifactCollection

    @property
    def TaskRunStateCache(self) -> type[orm_models.TaskRunStateCache]:
        """A task run state cache orm model"""
        return orm_models.TaskRunStateCache

    @property
    def Deployment(self) -> type[orm_models.Deployment]:
        """A deployment orm model"""
        return orm_models.Deployment

    @property
    def DeploymentSchedule(self) -> type[orm_models.DeploymentSchedule]:
        """A deployment schedule orm model"""
        return orm_models.DeploymentSchedule

    @property
    def SavedSearch(self) -> type[orm_models.SavedSearch]:
        """A saved search orm model"""
        return orm_models.SavedSearch

    @property
    def WorkPool(self) -> type[orm_models.WorkPool]:
        """A work pool orm model"""
        return orm_models.WorkPool

    @property
    def Worker(self) -> type[orm_models.Worker]:
        """A worker process orm model"""
        return orm_models.Worker

    @property
    def Log(self) -> type[orm_models.Log]:
        """A log orm model"""
        return orm_models.Log

    @property
    def ConcurrencyLimit(self) -> type[orm_models.ConcurrencyLimit]:
        """A concurrency model"""
        return orm_models.ConcurrencyLimit

    @property
    def ConcurrencyLimitV2(self) -> type[orm_models.ConcurrencyLimitV2]:
        """A v2 concurrency model"""
        return orm_models.ConcurrencyLimitV2

    @property
    def CsrfToken(self) -> type[orm_models.CsrfToken]:
        """A csrf token model"""
        return orm_models.CsrfToken

    @property
    def WorkQueue(self) -> type[orm_models.WorkQueue]:
        """A work queue model"""
        return orm_models.WorkQueue

    @property
    def Agent(self) -> type[orm_models.Agent]:
        """An agent model"""
        return orm_models.Agent

    @property
    def BlockType(self) -> type[orm_models.BlockType]:
        """A block type model"""
        return orm_models.BlockType

    @property
    def BlockSchema(self) -> type[orm_models.BlockSchema]:
        """A block schema model"""
        return orm_models.BlockSchema

    @property
    def BlockSchemaReference(self) -> type[orm_models.BlockSchemaReference]:
        """A block schema reference model"""
        return orm_models.BlockSchemaReference

    @property
    def BlockDocument(self) -> type[orm_models.BlockDocument]:
        """A block document model"""
        return orm_models.BlockDocument

    @property
    def BlockDocumentReference(self) -> type[orm_models.BlockDocumentReference]:
        """A block document reference model"""
        return orm_models.BlockDocumentReference

    @property
    def Configuration(self) -> type[orm_models.Configuration]:
        """An configuration model"""
        return orm_models.Configuration

    @property
    def Variable(self) -> type[orm_models.Variable]:
        """A variable model"""
        return orm_models.Variable

    @property
    def FlowRunInput(self) -> type[orm_models.FlowRunInput]:
        """A flow run input model"""
        return orm_models.FlowRunInput

    @property
    def Automation(self) -> type[orm_models.Automation]:
        """An automation model"""
        return orm_models.Automation

    @property
    def AutomationBucket(self) -> type[orm_models.AutomationBucket]:
        """An automation bucket model"""
        return orm_models.AutomationBucket

    @property
    def AutomationRelatedResource(self) -> type[orm_models.AutomationRelatedResource]:
        """An automation related resource model"""
        return orm_models.AutomationRelatedResource

    @property
    def CompositeTriggerChildFiring(
        self,
    ) -> type[orm_models.CompositeTriggerChildFiring]:
        """A model capturing a composite trigger's child firing"""
        return orm_models.CompositeTriggerChildFiring

    @property
    def AutomationEventFollower(self) -> type[orm_models.AutomationEventFollower]:
        """A model capturing one event following another event"""
        return orm_models.AutomationEventFollower

    @property
    def Event(self) -> type[orm_models.Event]:
        """An event model"""
        return orm_models.Event

    @property
    def EventResource(self) -> type[orm_models.EventResource]:
        """An event resource model"""
        return orm_models.EventResource
