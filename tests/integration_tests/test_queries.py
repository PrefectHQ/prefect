import os
import asyncio
from uuid import uuid4
import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas.states import State, StateType
from prefect.orion.models import orm


@pytest.fixture
async def fill_db(database_session, tests_dir):

    with open(tests_dir.joinpath("scripts", "populate_database.sql"), "r") as sql_file:
        raw_sql = sql_file.read().rstrip()
        stmts = raw_sql.split(";")

        async with database_session.begin():
            for stmt in stmts:
                if stmt:
                    await database_session.execute(sa.text(stmt))
