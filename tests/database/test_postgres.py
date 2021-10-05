import os

import pytest
import sqlalchemy as sa

from prefect import settings

pytestmark = pytest.mark.skipif(
    not settings.orion.database.connection_url.get_secret_value().startswith(
        "postgresql"
    ),
    reason="These tests apply only to Postgres",
)


@pytest.fixture
async def populate(session, tests_dir):

    with open(tests_dir.joinpath("scripts", "populate_database.sql"), "r") as sql_file:
        raw_sql = sql_file.read().rstrip()
        stmts = raw_sql.split(";")

        async with session.begin():
            for stmt in stmts:
                if stmt:
                    await session.execute(sa.text(stmt))
