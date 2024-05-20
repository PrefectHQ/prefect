import datetime
import inspect
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import dependencies
from prefect.server.database.configurations import (
    AioSqliteConfiguration,
    AsyncPostgresConfiguration,
    BaseDatabaseConfiguration,
)
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
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


@pytest.mark.parametrize(
    "ConnectionConfig",
    (AsyncPostgresConfiguration, AioSqliteConfiguration),
)
async def test_injecting_an_existing_database_database_config(ConnectionConfig):
    with dependencies.temporary_database_config(ConnectionConfig(None)):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) == ConnectionConfig


async def test_injecting_a_really_dumb_database_database_config():
    class UselessConfiguration(BaseDatabaseConfiguration):
        async def engine(self):
            ...

        async def session(self, engine):
            ...

        async def create_db(self, connection, base_metadata):
            ...

        async def drop_db(self, connection, base_metadata):
            ...

        def is_inmemory(self, engine):
            ...

        async def begin_transaction(self, session, locked):
            ...

    with dependencies.temporary_database_config(
        UselessConfiguration(connection_url=None)
    ):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) == UselessConfiguration


@pytest.mark.parametrize(
    "QueryComponents", (AsyncPostgresQueryComponents, AioSqliteQueryComponents)
)
async def test_injecting_existing_query_components(QueryComponents):
    with dependencies.temporary_query_components(QueryComponents()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) == QueryComponents


async def test_injecting_really_dumb_query_components():
    class ReallyBrokenQueries(BaseQueryComponents):
        # --- dialect-specific SqlAlchemy bindings

        def insert(self, obj):
            ...

        def greatest(self, *values):
            ...

        def least(self, *values):
            ...

        # --- dialect-specific JSON handling

        def uses_json_strings(self) -> bool:
            ...

        def cast_to_json(self, json_obj):
            ...

        def build_json_object(self, *args):
            ...

        def json_arr_agg(self, json_array):
            ...

        # --- dialect-optimized subqueries

        def make_timestamp_intervals(
            self,
            start_time,
            end_time,
            interval,
        ):
            ...

        def set_state_id_on_inserted_flow_runs_statement(
            self,
            fr_model,
            frs_model,
            inserted_flow_run_ids,
            insert_flow_run_states,
        ):
            ...

        async def get_flow_run_notifications_from_queue(self, session, limit):
            pass

        def get_scheduled_flow_runs_from_work_queues(
            self, limit_per_queue, work_queue_ids, scheduled_before
        ):
            ...

        def _get_scheduled_flow_runs_from_work_pool_template_path(self):
            ...

        async def flow_run_graph_v2(
            self,
            session: AsyncSession,
            flow_run_id: UUID,
            since: datetime,
            max_nodes: int,
        ) -> Graph:
            raise NotImplementedError()

    with dependencies.temporary_query_components(ReallyBrokenQueries()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) == ReallyBrokenQueries


@pytest.mark.parametrize(
    "ORMConfig", (AsyncPostgresORMConfiguration, AioSqliteORMConfiguration)
)
async def test_injecting_existing_orm_configs(ORMConfig):
    with dependencies.temporary_orm_config(ORMConfig()):
        db = dependencies.provide_database_interface()
        assert type(db.orm) == ORMConfig


async def test_inject_db(db):
    """
    Regression test for async-mangling behavior of inject_db() decorator.

    Previously, when wrapping a coroutine function, the decorator returned
    that function's coroutine object, instead of the coroutine function.

    This worked fine in most cases because both a coroutine function and a
    coroutine object can be awaited, but it broke our Pytest setup because
    we were auto-marking coroutine functions as async, and any async test
    wrapped by inject_db() was no longer a coroutine function, but instead
    a coroutine object, so we skipped marking it.
    """

    class Returner:
        @inject_db
        async def return_1(self, db):
            return 1

    assert inspect.iscoroutinefunction(Returner().return_1)


async def test_inject_interface_class():
    class TestInterface(PrefectDBInterface):
        @property
        def new_property(self):
            return 42

    with dependencies.temporary_interface_class(TestInterface):
        db = dependencies.provide_database_interface()
        assert isinstance(db, TestInterface)
