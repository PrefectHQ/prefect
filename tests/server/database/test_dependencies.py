import asyncio
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, dependencies
from prefect.server.database.configurations import (
    AioSqliteConfiguration,
    AsyncPostgresConfiguration,
    BaseDatabaseConfiguration,
)
from prefect.server.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
)
from prefect.server.database.query_components import (
    AioSqliteQueryComponents,
    AsyncPostgresQueryComponents,
    BaseQueryComponents,
)
from prefect.server.schemas.graph import Graph
from prefect.types._datetime import DateTime


@pytest.mark.parametrize(
    "ConnectionConfig",
    (AsyncPostgresConfiguration, AioSqliteConfiguration),
)
async def test_injecting_an_existing_database_database_config(ConnectionConfig):
    with dependencies.temporary_database_config(ConnectionConfig(None)):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) is ConnectionConfig


async def test_injecting_a_really_dumb_database_database_config():
    class UselessConfiguration(BaseDatabaseConfiguration):
        async def engine(self): ...

        async def session(self, engine): ...

        async def create_db(self, connection, base_metadata): ...

        async def drop_db(self, connection, base_metadata): ...

        def is_inmemory(self, engine): ...

        async def begin_transaction(self, session, locked): ...

    with dependencies.temporary_database_config(
        UselessConfiguration(connection_url=None)
    ):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) is UselessConfiguration


@pytest.mark.parametrize(
    "QueryComponents", (AsyncPostgresQueryComponents, AioSqliteQueryComponents)
)
async def test_injecting_existing_query_components(QueryComponents):
    with dependencies.temporary_query_components(QueryComponents()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) is QueryComponents


async def test_injecting_really_dumb_query_components():
    class ReallyBrokenQueries(BaseQueryComponents):
        # --- dialect-specific SqlAlchemy bindings

        def insert(self, obj): ...

        def greatest(self, *values): ...

        def least(self, *values): ...

        # --- dialect-specific JSON handling

        def uses_json_strings(self) -> bool: ...

        def cast_to_json(self, json_obj): ...

        def build_json_object(self, *args): ...

        def json_arr_agg(self, json_array): ...

        # --- dialect-optimized subqueries

        def make_timestamp_intervals(
            self,
            start_time,
            end_time,
            interval,
        ): ...

        def set_state_id_on_inserted_flow_runs_statement(
            self,
            fr_model,
            frs_model,
            inserted_flow_run_ids,
            insert_flow_run_states,
        ): ...

        def get_scheduled_flow_runs_from_work_queues(
            self, limit_per_queue, work_queue_ids, scheduled_before
        ): ...

        def _get_scheduled_flow_runs_from_work_pool_template_path(self): ...

        def _build_flow_run_graph_v2_query(self): ...

        async def flow_run_graph_v2(
            self,
            session: AsyncSession,
            flow_run_id: UUID,
            since: DateTime,
            max_nodes: int,
        ) -> Graph:
            raise NotImplementedError()

    with dependencies.temporary_query_components(ReallyBrokenQueries()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) is ReallyBrokenQueries


@pytest.mark.parametrize(
    "ORMConfig", (AsyncPostgresORMConfiguration, AioSqliteORMConfiguration)
)
async def test_injecting_existing_orm_configs(ORMConfig):
    with dependencies.temporary_orm_config(ORMConfig()):
        db = dependencies.provide_database_interface()
        assert type(db.orm) is ORMConfig


async def test_inject_interface_class():
    class TestInterface(PrefectDBInterface):
        @property
        def new_property(self):
            return 42

    with dependencies.temporary_interface_class(TestInterface):
        db = dependencies.provide_database_interface()
        assert isinstance(db, TestInterface)


class TestDBInject:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.db: PrefectDBInterface = dependencies.provide_database_interface()

    def test_decorated_function(self):
        @dependencies.db_injector
        def function_with_injected_db(
            db: PrefectDBInterface, foo: int
        ) -> PrefectDBInterface:
            """The documentation is sublime"""
            return db

        assert function_with_injected_db(42) is self.db

        unwrapped = function_with_injected_db.__wrapped__
        assert function_with_injected_db.__doc__ == unwrapped.__doc__
        function_with_injected_db.__doc__ = "Something else"
        assert function_with_injected_db.__doc__ == "Something else"
        assert unwrapped.__doc__ == function_with_injected_db.__doc__
        del function_with_injected_db.__doc__
        assert function_with_injected_db.__doc__ is None
        assert unwrapped.__doc__ is function_with_injected_db.__doc__

    class SomeClass:
        @dependencies.db_injector
        def method_with_injected_db(
            self, db: PrefectDBInterface, foo: int
        ) -> PrefectDBInterface:
            """The documentation is sublime"""
            return db

    def test_decorated_method(self):
        instance = self.SomeClass()
        assert instance.method_with_injected_db(42) is self.db

    def test_unbound_decorated_method(self):
        instance = self.SomeClass()
        # manually binding the unbound descriptor to an instance
        bound = self.SomeClass.method_with_injected_db.__get__(instance)
        assert bound(42) is self.db

    def test_bound_method_attributes(self):
        instance = self.SomeClass()
        bound = instance.method_with_injected_db
        assert bound.__self__ is instance
        assert bound.__func__ is self.SomeClass.method_with_injected_db.__wrapped__

        unwrapped = bound.__wrapped__
        assert bound.__doc__ == unwrapped.__doc__

        before = bound.__doc__
        with pytest.raises(AttributeError, match="is not writable$"):
            bound.__doc__ = "Something else"
        with pytest.raises(AttributeError, match="is not writable$"):
            del bound.__doc__
        assert unwrapped.__doc__ == before

    def test_decorated_coroutine_function(self):
        @dependencies.db_injector
        async def coroutine_with_injected_db(
            db: PrefectDBInterface, foo: int
        ) -> PrefectDBInterface:
            return db

        assert asyncio.iscoroutinefunction(coroutine_with_injected_db)
        assert asyncio.run(coroutine_with_injected_db(42)) is self.db
