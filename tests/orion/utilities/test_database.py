import datetime
import enum
import math
from typing import List

import pendulum
import pydantic
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from prefect.orion.database.configurations import AioSqliteConfiguration
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import AioSqliteORMConfiguration
from prefect.orion.database.query_components import AioSqliteQueryComponents
from prefect.orion.utilities.database import (
    JSON,
    Pydantic,
    Timestamp,
    date_add,
    date_diff,
    interval_add,
    json_contains,
    json_has_all_keys,
    json_has_any_key,
)

DBBase = declarative_base()


class PydanticModel(pydantic.BaseModel):
    x: int
    y: datetime.datetime = pydantic.Field(default_factory=lambda: pendulum.now("UTC"))


class Color(enum.Enum):
    RED = "RED"
    BLUE = "BLUE"


class SQLPydanticModel(DBBase):
    __tablename__ = "_test_pydantic_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    data = sa.Column(Pydantic(PydanticModel))
    data_list = sa.Column(Pydantic(List[PydanticModel]))
    color = sa.Column(Pydantic(Color, sa_column_type=sa.Text()))


class SQLTimestampModel(DBBase):
    __tablename__ = "_test_timestamp_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    ts_1 = sa.Column(Timestamp)
    ts_2 = sa.Column(Timestamp)
    i_1 = sa.Column(sa.Interval)
    i_2 = sa.Column(sa.Interval)


class SQLJSONModel(DBBase):
    __tablename__ = "_test_json_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    data = sa.Column(JSON)


@pytest.fixture(scope="module", autouse=True)
async def create_database_models(database_engine):
    """
    Add the models defined in this file to the database
    """
    async with database_engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.create_all)

    try:
        yield
    finally:
        async with database_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.drop_all)


@pytest.fixture(scope="function", autouse=True)
async def clear_database_models(database_engine):
    """
    Clears the models defined in this file
    """
    yield
    async with database_engine.begin() as conn:
        for table in reversed(DBBase.metadata.sorted_tables):
            await conn.execute(table.delete())


class TestPydantic:
    async def test_write_to_Pydantic(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data=p_model)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)
        assert results[0].data.y < pendulum.now("UTC")

    async def test_write_dict_to_Pydantic(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data=p_model.dict())
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)

    async def test_nullable_Pydantic(self, session):
        s_model = SQLPydanticModel(data=None)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert results[0].data is None

    async def test_generic_model(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data_list=[p_model])
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data_list[0], PydanticModel)
        assert results[0].data_list == [p_model]

    async def test_generic_model_validates(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data_list=p_model)
        session.add(s_model)
        with pytest.raises(sa.exc.StatementError, match="(validation error)"):
            await session.flush()

    async def test_write_to_enum_field(self, session):
        s_model = SQLPydanticModel(color="RED")
        session.add(s_model)
        await session.flush()

    async def test_write_to_enum_field_is_validated(self, session):
        s_model = SQLPydanticModel(color="GREEN")
        session.add(s_model)
        with pytest.raises(sa.exc.StatementError, match="(validation error)"):
            await session.flush()

    async def test_enum_field_is_a_string_in_database(self, session):
        s_model = SQLPydanticModel(color="RED")
        session.add(s_model)
        await session.flush()

        # write to the field, since it is an arbitrary string
        await session.execute(
            f"""
            UPDATE {SQLPydanticModel.__tablename__}
            SET color = 'GREEN';
            """
        )

        # enum enforced by application
        stmt = sa.select(SQLPydanticModel)
        with pytest.raises(
            pydantic.ValidationError, match="(not a valid enumeration member)"
        ):
            await session.execute(stmt)


class TestTimestamp:
    async def test_error_if_naive_timestamp_passed(self, session):
        model = SQLTimestampModel(ts_1=datetime.datetime(2000, 1, 1))
        session.add(model)
        with pytest.raises(sa.exc.StatementError, match="(must have a timezone)"):
            await session.flush()

    async def test_timestamp_converted_to_utc(self, session):
        model = SQLTimestampModel(
            ts_1=datetime.datetime(2000, 1, 1, tzinfo=pendulum.timezone("EST"))
        )
        session.add(model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLTimestampModel))
        results = query.scalars().all()
        assert results[0].ts_1 == model.ts_1
        assert results[0].ts_1.tzinfo == pendulum.timezone("UTC")


class TestJSON:
    @pytest.fixture(autouse=True)
    async def data(self, session):
        session.add_all(
            [
                SQLJSONModel(id=1, data=["a"]),
                SQLJSONModel(id=2, data=["b"]),
                SQLJSONModel(id=3, data=["a", "b", "c"]),
                SQLJSONModel(id=4, data=["a", "b", {"c": "d"}]),
                SQLJSONModel(id=5, data=["d", 2, 3]),
                SQLJSONModel(id=6, data=["d", [2], 3]),
            ]
        )
        await session.commit()

    async def get_ids(self, session, query):
        result = await session.execute(query)
        return [r.id for r in result.scalars().all()]

    @pytest.mark.parametrize(
        "keys,ids",
        [
            (["a"], [1, 3, 4]),
            (["b"], [2, 3, 4]),
            (["a", "c"], [3]),
            ([{"c": "d"}], [4]),
            ([{"c": "x"}], []),
            ([{"x": "d"}], []),
            (["x"], []),
            # this is based on Postgres operator behavior
            ([], [1, 2, 3, 4, 5, 6]),
            ([2], [5]),
            ([[2]], [6]),
            ([[2], 3], [6]),
            # Postgres disregards repeated keys
            (["a", "a", "a"], [1, 3, 4]),
        ],
    )
    async def test_json_contains_right_side_literal(self, session, keys, ids):
        query = (
            sa.select(SQLJSONModel)
            .where(json_contains(SQLJSONModel.data, keys))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    @pytest.mark.parametrize(
        "keys,ids",
        [
            (["a"], [1]),
            (["b"], [2]),
            (["a", "c"], [1]),
            (["a", "b", "c"], [1, 2, 3]),
            (["a", "b", "c", "d"], [1, 2, 3]),
            (["d", [2], 3, 4, 5, 6], [6]),
            # tests to make sure SQLite counting logic doesn't double-count
            (["a", "a", "a"], [1]),
        ],
    )
    async def test_json_contains_left_side_literal(self, session, keys, ids):
        query = (
            sa.select(SQLJSONModel)
            .where(json_contains(keys, SQLJSONModel.data))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    @pytest.mark.parametrize(
        "left,right,match",
        [
            (["a"], ["a"], True),
            (["a", "b"], ["a"], True),
            (["a", "b"], ["a", "b"], True),
            (["a"], ["a", "b"], False),
        ],
    )
    async def test_json_contains_both_sides_literal(self, session, left, right, match):
        query = sa.select(sa.literal("match")).where(json_contains(left, right))
        result = await session.execute(query)
        assert (result.scalar() == "match") == match

    @pytest.mark.parametrize(
        "id_for_keys,ids_for_results",
        [
            [1, [1, 3, 4]],
            [3, [3]],
        ],
    )
    async def test_json_contains_both_sides_columns(
        self, session, id_for_keys, ids_for_results
    ):

        query = (
            sa.select(SQLJSONModel)
            .where(
                json_contains(
                    SQLJSONModel.data,
                    # select the data corresponding to the `id_for_keys` id
                    sa.select(SQLJSONModel.data)
                    .where(SQLJSONModel.id == id_for_keys)
                    .scalar_subquery(),
                )
            )
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids_for_results

    @pytest.mark.parametrize(
        "keys,ids",
        [
            (["a"], [1, 3, 4]),
            (["b"], [2, 3, 4]),
            (["a", "b"], [1, 2, 3, 4]),
            (["c"], [3]),
            (["c", "d"], [3, 5, 6]),
            (["x"], []),
            ([], []),
        ],
    )
    async def test_json_has_any_key(self, session, keys, ids):
        query = (
            sa.select(SQLJSONModel)
            .where(json_has_any_key(SQLJSONModel.data, keys))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    async def test_multiple_json_has_any(self, session):
        """
        SQLAlchemy's default bindparam has a `.` in it, which SQLite rejects. We
        create a custom bindparam name with `unique=True` to avoid confusion;
        this tests that multiple json_has_any_key clauses can be used in the
        same query.
        """
        query = (
            sa.select(SQLJSONModel)
            .where(
                sa.or_(
                    sa.and_(
                        json_has_any_key(SQLJSONModel.data, ["a"]),
                        json_has_any_key(SQLJSONModel.data, ["b"]),
                    ),
                    json_has_any_key(SQLJSONModel.data, ["c"]),
                    json_has_any_key(SQLJSONModel.data, ["d"]),
                ),
            )
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == [3, 4, 5, 6]

    @pytest.mark.parametrize(
        "keys,ids",
        [
            (["a"], [1, 3, 4]),
            (["b"], [2, 3, 4]),
            (["a", "c"], [3]),
            (["x"], []),
            ([], [1, 2, 3, 4, 5, 6]),
        ],
    )
    async def test_json_has_all_keys(self, session, keys, ids):
        query = (
            sa.select(SQLJSONModel)
            .where(json_has_all_keys(SQLJSONModel.data, keys))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    async def test_json_has_all_keys_requires_scalar_inputs(self):
        with pytest.raises(ValueError, match="(values must be strings)"):
            json_has_all_keys(SQLJSONModel.data, ["a", 3])

    async def test_json_has_any_key_requires_scalar_inputs(self):
        with pytest.raises(ValueError, match="(values must be strings)"):
            json_has_any_key(SQLJSONModel.data, ["a", 3])

    async def test_json_functions_use_postgres_operators_with_postgres(self):
        dialect = sa.dialects.postgresql.dialect()

        extract_statement = SQLJSONModel.data["x"].compile(dialect=dialect)
        contains_stmt = json_contains(SQLJSONModel.data, ["x"]).compile(dialect=dialect)
        any_stmt = json_has_any_key(SQLJSONModel.data, ["x"]).compile(dialect=dialect)
        all_stmt = json_has_all_keys(SQLJSONModel.data, ["x"]).compile(dialect=dialect)

        assert "->" in str(extract_statement)
        assert "JSON_EXTRACT" not in str(extract_statement)
        assert "@>" in str(contains_stmt)
        assert "json_each" not in str(contains_stmt)
        assert "?|" in str(any_stmt)
        assert "json_each" not in str(any_stmt)
        assert "?&" in str(all_stmt)
        assert "json_each" not in str(all_stmt)

    async def test_json_functions_dont_use_postgres_operators_with_sqlite(self):
        dialect = sa.dialects.sqlite.dialect()

        extract_statement = SQLJSONModel.data["x"].compile(dialect=dialect)
        contains_stmt = json_contains(SQLJSONModel.data, ["x"]).compile(dialect=dialect)
        any_stmt = json_has_any_key(SQLJSONModel.data, ["x"]).compile(dialect=dialect)
        all_stmt = json_has_all_keys(SQLJSONModel.data, ["x"]).compile(dialect=dialect)

        assert "->" not in str(extract_statement)
        assert "JSON_EXTRACT" in str(extract_statement)
        assert "@>" not in str(contains_stmt)
        assert "json_each" in str(contains_stmt)
        assert "?|" not in str(any_stmt)
        assert "json_each" in str(any_stmt)
        assert "?&" not in str(all_stmt)
        assert "json_each" in str(all_stmt)

    @pytest.mark.parametrize("extrema", [-math.inf, math.nan, +math.inf])
    async def test_json_floating_point_extrema(
        self, session: AsyncSession, extrema: float
    ):
        example = SQLJSONModel(id=100, data=[-1.0, extrema, 1.0])
        session.add(example)
        await session.flush()
        session.expire(example)

        result = await session.execute(
            sa.select(SQLJSONModel).where(SQLJSONModel.id == 100)
        )
        from_db: SQLJSONModel = result.scalars().first()
        assert from_db.data == [-1.0, None, 1.0]


class TestDateFunctions:
    """Test combinations of Python literals and DB columns"""

    @pytest.fixture(autouse=True)
    async def create_data(self, session):

        model = SQLTimestampModel(
            ts_1=pendulum.datetime(2021, 1, 1),
            ts_2=pendulum.datetime(2021, 1, 4, 0, 5),
            i_1=datetime.timedelta(days=3, minutes=5),
            i_2=datetime.timedelta(hours=1, minutes=-17),
        )
        session.add(model)
        await session.commit()

    @pytest.mark.parametrize(
        "ts_1, i_1",
        [
            (pendulum.datetime(2021, 1, 1), datetime.timedelta(days=3, minutes=5)),
            (pendulum.datetime(2021, 1, 1), SQLTimestampModel.i_1),
            (SQLTimestampModel.ts_1, datetime.timedelta(days=3, minutes=5)),
            (SQLTimestampModel.ts_1, SQLTimestampModel.i_1),
        ],
    )
    async def test_date_add(self, session, ts_1, i_1):
        result = await session.execute(
            sa.select(date_add(ts_1, i_1)).select_from(SQLTimestampModel)
        )
        assert result.scalar() == pendulum.datetime(2021, 1, 4, 0, 5)

    @pytest.mark.parametrize(
        "ts_1, ts_2",
        [
            (pendulum.datetime(2021, 1, 1), pendulum.datetime(2021, 1, 4, 0, 5)),
            (pendulum.datetime(2021, 1, 1), SQLTimestampModel.ts_2),
            (SQLTimestampModel.ts_1, pendulum.datetime(2021, 1, 4, 0, 5)),
            (SQLTimestampModel.ts_1, SQLTimestampModel.ts_2),
        ],
    )
    async def test_date_diff(self, session, ts_1, ts_2):
        result = await session.execute(
            sa.select(date_diff(ts_2, ts_1)).select_from(SQLTimestampModel)
        )
        assert result.scalar() == datetime.timedelta(days=3, minutes=5)

    @pytest.mark.parametrize(
        "i_1, i_2",
        [
            (
                datetime.timedelta(days=3, minutes=5),
                datetime.timedelta(hours=1, minutes=-17),
            ),
            (datetime.timedelta(days=3, minutes=5), SQLTimestampModel.i_2),
            (SQLTimestampModel.i_1, datetime.timedelta(hours=1, minutes=-17)),
            (SQLTimestampModel.i_1, SQLTimestampModel.i_2),
        ],
    )
    async def test_interval_add(self, session, i_1, i_2):
        result = await session.execute(
            sa.select(interval_add(i_1, i_2)).select_from(SQLTimestampModel)
        )
        assert result.scalar() == datetime.timedelta(days=3, minutes=48)


async def test_error_thrown_if_sqlite_version_is_below_minimum(monkeypatch):
    monkeypatch.setattr("sqlite3.sqlite_version_info", (3, 23, 9))
    monkeypatch.setattr("sqlite3.sqlite_version", "3.23.9")
    with pytest.raises(
        RuntimeError,
        match="Orion requires sqlite >= 3.24.0 but we found version 3.23.9",
    ):

        db = OrionDBInterface(
            database_config=AioSqliteConfiguration(
                connection_url="sqlite+aiosqlite:///file::memory",
            ),
            query_components=AioSqliteQueryComponents(),
            orm=AioSqliteORMConfiguration(),
        )
        await db.engine()
