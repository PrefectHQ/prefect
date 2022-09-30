import inspect
from pathlib import Path

import pytest
import sqlalchemy as sa

from prefect.orion.database import dependencies
from prefect.orion.database.configurations import (
    AioSqliteConfiguration,
    AsyncPostgresConfiguration,
    BaseDatabaseConfiguration,
)
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
    BaseORMConfiguration,
)
from prefect.orion.database.query_components import (
    AioSqliteQueryComponents,
    AsyncPostgresQueryComponents,
    BaseQueryComponents,
)


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
            self, db, limit_per_queue, work_queue_ids, scheduled_before
        ):
            ...

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


async def test_injecting_really_dumb_orm_configuration():
    class UselessORMConfiguration(BaseORMConfiguration):
        def run_migrations(self):
            ...

        @property
        def versions_dir(self):
            return Path("")

    class UselessBaseMixin:
        my_string_column = sa.Column(
            sa.String, nullable=False, default="Mostly harmless"
        )

    with dependencies.temporary_orm_config(
        UselessORMConfiguration(
            base_metadata=sa.schema.MetaData(schema="new_schema"),
            base_model_mixins=[UselessBaseMixin],
        )
    ):
        db = dependencies.provide_database_interface()
        assert type(db.orm) == UselessORMConfiguration

        # base mixins should be used to create orm models
        assert "my_string_column" in db.Flow.__table__.columns.keys()
        # base metadata should specify a different schema
        assert db.Base.metadata.schema == "new_schema"

    # orm properties should be unset after we exit context
    db = dependencies.provide_database_interface()
    assert "my_string_column" not in db.Flow.__table__.columns.keys()
    assert db.Base.metadata.schema != "new_schema"


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
    class TestInterface(OrionDBInterface):
        @property
        def new_property(self):
            return 42

    with dependencies.temporary_interface_class(TestInterface):
        db = dependencies.provide_database_interface()
        assert isinstance(db, TestInterface)
