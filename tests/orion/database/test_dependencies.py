import pytest
import sqlalchemy as sa

from prefect.orion.database import dependencies
from prefect.orion.database.configurations import (
    BaseDatabaseConfiguration,
    AsyncPostgresConfiguration,
    AioSqliteConfiguration,
)
from prefect.orion.database.query_components import (
    BaseQueryComponents,
    AsyncPostgresQueryComponents,
    AioSqliteQueryComponents,
)
from prefect.orion.database.orm_models import (
    BaseORMConfiguration,
    AsyncPostgresORMConfiguration,
    AioSqliteORMConfiguration,
)


@pytest.mark.parametrize(
    "ConnectionConfig",
    (AsyncPostgresConfiguration, AioSqliteConfiguration),
)
async def test_injecting_an_existing_database_database_config(ConnectionConfig):
    async with dependencies.temporary_database_config(ConnectionConfig()):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) == ConnectionConfig


async def test_injecting_a_really_dumb_database_database_config():
    class UselessConfiguration(BaseDatabaseConfiguration):
        async def engine(
            self,
        ):
            ...

        async def session(self, engine):
            ...

        async def create_db(self, connection, base_metadata):
            ...

        async def drop_db(self, connection, base_metadata):
            ...

        def is_inmemory(self, engine):
            ...

    async with dependencies.temporary_database_config(
        UselessConfiguration(connection_url=None)
    ):
        db = dependencies.provide_database_interface()
        assert type(db.database_config) == UselessConfiguration


@pytest.mark.parametrize(
    "QueryComponents", (AsyncPostgresQueryComponents, AioSqliteQueryComponents)
)
async def test_injecting_existing_query_components(QueryComponents):
    async with dependencies.temporary_query_components(QueryComponents()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) == QueryComponents


async def test_injecting_really_dumb_query_components():
    class ReallyBrokenQueries(BaseQueryComponents):
        # --- dialect-specific SqlAlchemy bindings

        def insert(self, obj):
            ...

        def greatest(self, *values):
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

    async with dependencies.temporary_query_components(ReallyBrokenQueries()):
        db = dependencies.provide_database_interface()
        assert type(db.queries) == ReallyBrokenQueries


@pytest.mark.parametrize(
    "ORMConfig", (AsyncPostgresORMConfiguration, AioSqliteORMConfiguration)
)
async def test_injecting_existing_orm_configs(ORMConfig):
    async with dependencies.temporary_orm_config(ORMConfig()):
        db = dependencies.provide_database_interface()
        assert type(db.orm) == ORMConfig


async def test_injecting_really_dumb_orm_configuration():
    class UselessORMConfiguration(BaseORMConfiguration):
        def run_migrations(self):
            ...

    class UselessBaseMixin:
        my_string_column = sa.Column(
            sa.String, nullable=False, default="Mostly harmless"
        )

    async with dependencies.temporary_orm_config(
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
