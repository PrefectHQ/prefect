import datetime
import enum
import math
import sqlite3
from typing import Any, Optional, Union
from unittest import mock

import pydantic
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

from prefect.server.database import PrefectDBInterface
from prefect.server.database.configurations import AioSqliteConfiguration
from prefect.server.database.orm_models import AioSqliteORMConfiguration
from prefect.server.database.query_components import AioSqliteQueryComponents
from prefect.server.utilities.database import (
    JSON,
    Pydantic,
    Timestamp,
    bindparams_from_clause,
)

DBBase = declarative_base(type_annotation_map={datetime.datetime: Timestamp})


class PydanticModel(pydantic.BaseModel):
    x: int
    y: datetime.datetime = pydantic.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class Color(enum.Enum):
    RED = "RED"
    BLUE = "BLUE"


class SQLPydanticModel(DBBase):
    __tablename__ = "_test_pydantic_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[Optional[PydanticModel]] = mapped_column(Pydantic(PydanticModel))
    data_list: Mapped[Optional[list[PydanticModel]]] = mapped_column(
        Pydantic(list[PydanticModel])
    )
    color: Mapped[Optional[Color]] = mapped_column(
        Pydantic(Color, sa_column_type=sa.Text())
    )


class SQLTimestampModel(DBBase):
    __tablename__ = "_test_timestamp_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_1: Mapped[Optional[datetime.datetime]]
    ts_2: Mapped[Optional[datetime.datetime]]
    i_1: Mapped[Optional[datetime.timedelta]]
    i_2: Mapped[Optional[datetime.timedelta]]


class SQLJSONModel(DBBase):
    __tablename__ = "_test_json_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[Any] = mapped_column(JSON)


@pytest.fixture(scope="module", autouse=True)
async def create_database_models(database_engine: AsyncEngine):
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
async def clear_database_models(db: PrefectDBInterface):
    """
    Clears the models defined in this file
    """
    yield
    async with db.session_context(begin_transaction=True) as session:
        for table in reversed(DBBase.metadata.sorted_tables):
            await session.execute(table.delete())


class TestPydantic:
    async def test_write_to_Pydantic(self, session: AsyncSession):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data=p_model)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.scalars(sa.select(SQLPydanticModel))
        results = query.all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)
        assert results[0].data.y < datetime.datetime.now(datetime.timezone.utc)

    async def test_write_dict_to_Pydantic(self, session: AsyncSession):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data=p_model.model_dump())
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.scalars(sa.select(SQLPydanticModel))
        results = query.all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)

    async def test_nullable_Pydantic(self, session: AsyncSession):
        s_model = SQLPydanticModel(data=None)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.scalars(sa.select(SQLPydanticModel))
        results = query.all()
        assert len(results) == 1
        assert results[0].data is None

    async def test_generic_model(self, session: AsyncSession):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data_list=[p_model])
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.scalars(sa.select(SQLPydanticModel))
        results = query.all()
        assert len(results) == 1
        assert results[0].data_list is not None
        assert isinstance(results[0].data_list[0], PydanticModel)
        assert results[0].data_list == [p_model]

    async def test_generic_model_validates(self, session: AsyncSession):
        p_model = PydanticModel(x=100)
        s_model = SQLPydanticModel(data_list=p_model)
        session.add(s_model)
        with pytest.raises(sa.exc.StatementError, match="(validation error)"):
            await session.flush()

    async def test_write_to_enum_field(self, session: AsyncSession):
        s_model = SQLPydanticModel(color="RED")
        session.add(s_model)
        await session.flush()

    async def test_write_to_enum_field_is_validated(self, session: AsyncSession):
        s_model = SQLPydanticModel(color="GREEN")
        session.add(s_model)
        with pytest.raises(sa.exc.StatementError, match="(validation error)"):
            await session.flush()

    async def test_enum_field_is_a_string_in_database(self, session: AsyncSession):
        s_model = SQLPydanticModel(color="RED")
        session.add(s_model)
        await session.flush()

        # write to the field, since it is an arbitrary string
        await session.execute(
            sa.text(
                f"""
            UPDATE {SQLPydanticModel.__tablename__}
            SET color = 'GREEN';
            """
            )
        )

        # enum enforced by application
        stmt = sa.select(SQLPydanticModel)
        with pytest.raises(pydantic.ValidationError):
            await session.execute(stmt)


class TestTimestamp:
    async def test_error_if_naive_timestamp_passed(self, session: AsyncSession):
        model = SQLTimestampModel(ts_1=datetime.datetime(2000, 1, 1))
        session.add(model)
        with pytest.raises(sa.exc.StatementError, match="(must have a timezone)"):
            await session.flush()

    async def test_timestamp_converted_to_utc(self, session: AsyncSession):
        model = SQLTimestampModel(
            ts_1=datetime.datetime(
                2000, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
            )
        )
        session.add(model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.scalars(sa.select(SQLTimestampModel))
        results = query.all()
        assert results[0].ts_1 == model.ts_1
        assert results[0].ts_1 is not None
        assert results[0].ts_1.utcoffset() == datetime.timedelta(0)


class TestJSON:
    @pytest.fixture(autouse=True)
    async def data(self, session: AsyncSession):
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

    async def get_ids(
        self, session: AsyncSession, query: sa.Select[tuple[SQLJSONModel]]
    ) -> list[int]:
        result = await session.scalars(query)
        return [r.id for r in result]

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
    async def test_json_contains_right_side_literal(
        self, session: AsyncSession, keys: list[Any], ids: list[int]
    ):
        query = (
            sa.select(SQLJSONModel)
            .where(SQLJSONModel.data.contains(keys))
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
    async def test_json_contains_left_side_literal(
        self, session: AsyncSession, keys: list[Any], ids: list[int]
    ):
        query = (
            sa.select(SQLJSONModel)
            .where(sa.bindparam("keys", keys, type_=JSON).contains(SQLJSONModel.data))
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
    async def test_json_contains_both_sides_literal(
        self, session: AsyncSession, left: list[str], right: list[str], match: bool
    ):
        query = sa.select(sa.literal("match")).where(
            sa.bindparam("left", left, type_=JSON).contains(right)
        )
        result = await session.scalar(query)
        assert (result == "match") is match

    @pytest.mark.parametrize(
        "id_for_keys,ids_for_results",
        [
            [1, [1, 3, 4]],
            [3, [3]],
        ],
    )
    async def test_json_contains_both_sides_columns(
        self, session: AsyncSession, id_for_keys: list[Any], ids_for_results: list[Any]
    ):
        query = (
            sa.select(SQLJSONModel)
            .where(
                SQLJSONModel.data.contains(
                    # select the data corresponding to the `id_for_keys` id
                    sa.select(SQLJSONModel.data)
                    .where(SQLJSONModel.id == id_for_keys)
                    .scalar_subquery()
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
    async def test_json_has_any_key(
        self, session: AsyncSession, keys: list[str], ids: list[int]
    ):
        query = (
            sa.select(SQLJSONModel)
            .where(SQLJSONModel.data.has_any(sa.cast(array(keys), ARRAY(sa.String))))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    async def test_multiple_json_has_any(self, session: AsyncSession):
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
                        SQLJSONModel.data.has_any(array(["a"])),
                        SQLJSONModel.data.has_any(array(["b"])),
                    ),
                    SQLJSONModel.data.has_any(array(["c"])),
                    SQLJSONModel.data.has_any(array(["d"])),
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
    async def test_json_has_all_keys(
        self, session: AsyncSession, keys: list[str], ids: list[int]
    ):
        query = (
            sa.select(SQLJSONModel)
            .where(SQLJSONModel.data.has_all(sa.cast(array(keys), ARRAY(sa.String()))))
            .order_by(SQLJSONModel.id)
        )
        assert await self.get_ids(session, query) == ids

    async def test_json_functions_use_postgres_operators_with_postgres(self):
        dialect = sa.dialects.postgresql.dialect()

        extract_statement = SQLJSONModel.data["x"].compile(dialect=dialect)
        alt_extract_statement = SQLJSONModel.data["x"].astext.compile(dialect=dialect)
        contains_stmt = SQLJSONModel.data.contains(["x"]).compile(dialect=dialect)
        any_stmt = SQLJSONModel.data.has_any(array(["x"])).compile(dialect=dialect)
        all_stmt = SQLJSONModel.data.has_all(array(["x"])).compile(dialect=dialect)

        assert ".data -> " in str(extract_statement)
        assert ".data ->> " in str(alt_extract_statement)
        assert ".data @> " in str(contains_stmt)
        assert ".data ?| " in str(any_stmt)
        assert ".data ?& " in str(all_stmt)

    async def test_json_functions_dont_use_postgres_operators_with_sqlite(self):
        dialect = sa.dialects.sqlite.dialect()

        extract_statement = SQLJSONModel.data["x"].compile(dialect=dialect)
        alt_extract_statement = SQLJSONModel.data["x"].astext.compile(dialect=dialect)
        contains_stmt = SQLJSONModel.data.contains(["x"]).compile(dialect=dialect)
        any_stmt = SQLJSONModel.data.has_any(array(["x"])).compile(dialect=dialect)
        all_stmt = SQLJSONModel.data.has_all(array(["x"])).compile(dialect=dialect)

        assert ".data ->" not in str(extract_statement)
        assert ".data ->>" not in str(alt_extract_statement)
        assert ".data @>" not in str(contains_stmt)
        assert ".data ?|" not in str(any_stmt)
        assert ".data ?&" not in str(all_stmt)

    async def test_sqlite_json_extract_as_json_extract(self):
        dialect = sa.dialects.sqlite.dialect()
        extract_statement = SQLJSONModel.data["x.y.z"].astext.compile(dialect=dialect)
        assert "->>" not in str(extract_statement)
        assert "JSON_EXTRACT" in str(extract_statement)

    async def test_postgres_json_extract_as_native_operator(self):
        dialect = sa.dialects.postgresql.dialect()
        extract_statement = SQLJSONModel.data["x.y.z"].astext.compile(dialect=dialect)
        assert "->>" in str(extract_statement)

    @pytest.mark.parametrize("extrema", [-math.inf, math.nan, +math.inf])
    async def test_json_floating_point_extrema(
        self, session: AsyncSession, extrema: float
    ):
        example = SQLJSONModel(id=100, data=[-1.0, extrema, 1.0])
        session.add(example)
        await session.flush()
        session.expire(example)

        result = await session.scalar(
            sa.select(SQLJSONModel).where(SQLJSONModel.id == 100)
        )
        assert result is not None
        assert result.data == [-1.0, None, 1.0]


class TestCustomFunctions:
    def test_sqlite_now_compilation(self) -> None:
        dialect = sa.dialects.sqlite.dialect()
        expression = sa.func.now()
        compiled = expression.compile(
            dialect=dialect, compile_kwargs={"render_postcompile": True}
        )
        assert str(compiled) == "strftime('%Y-%m-%d %H:%M:%f000', 'now')"

    @pytest.mark.parametrize(
        "dialect,expected_function",
        (
            (sa.dialects.sqlite.dialect(), "max"),
            (sa.dialects.postgresql.dialect(), "greatest"),
        ),
    )
    def test_greatest_compilation(
        self, dialect: sa.Dialect, expected_function: str
    ) -> None:
        expression = sa.func.greatest(17, 42, 11)
        compiled = str(expression.compile(dialect=dialect))
        assert compiled.partition("(")[0] == expected_function


class TestDateFunctions:
    """Test combinations of Python literals and DB columns"""

    @pytest.fixture(autouse=True)
    async def create_data(self, session: AsyncSession):
        model = SQLTimestampModel(
            ts_1=datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
            ts_2=datetime.datetime(2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc),
            i_1=datetime.timedelta(days=3, minutes=5),
            i_2=datetime.timedelta(hours=1, minutes=-17),
        )
        session.add(model)
        await session.commit()

    @pytest.mark.parametrize(
        "ts_1, i_1",
        [
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.timedelta(days=3, minutes=5),
            ),
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                SQLTimestampModel.i_1,
            ),
            (SQLTimestampModel.ts_1, datetime.timedelta(days=3, minutes=5)),
            (SQLTimestampModel.ts_1, SQLTimestampModel.i_1),
        ],
    )
    async def test_date_add(
        self,
        session: AsyncSession,
        ts_1: Union[datetime.datetime, sa.Column[datetime.datetime]],
        i_1: Union[datetime.timedelta, sa.Column[datetime.timedelta]],
    ):
        result = await session.scalar(
            sa.select(sa.func.date_add(ts_1, i_1)).select_from(SQLTimestampModel)
        )
        assert result == datetime.datetime(
            2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc
        )

    @pytest.mark.parametrize(
        "ts_1, ts_2",
        [
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc),
            ),
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                SQLTimestampModel.ts_2,
            ),
            (
                SQLTimestampModel.ts_1,
                datetime.datetime(2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc),
            ),
            (SQLTimestampModel.ts_1, SQLTimestampModel.ts_2),
        ],
    )
    async def test_date_diff(
        self,
        session: AsyncSession,
        ts_1: Union[datetime.datetime, sa.Column[datetime.datetime]],
        ts_2: Union[datetime.datetime, sa.Column[datetime.datetime]],
    ):
        result = await session.scalar(
            sa.select(sa.func.date_diff(ts_2, ts_1)).select_from(SQLTimestampModel)
        )
        assert result == datetime.timedelta(days=3, minutes=5)

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
    async def test_interval_add(
        self,
        session: AsyncSession,
        i_1: Union[datetime.timedelta, sa.Column[datetime.timedelta]],
        i_2: Union[datetime.timedelta, sa.Column[datetime.timedelta]],
    ):
        result = await session.scalar(
            sa.select(sa.func.interval_add(i_1, i_2)).select_from(SQLTimestampModel)
        )
        assert result == datetime.timedelta(days=3, minutes=48)

    @pytest.mark.parametrize(
        "ts_1, ts_2",
        [
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc),
            ),
            (
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                SQLTimestampModel.ts_2,
            ),
            (
                SQLTimestampModel.ts_1,
                datetime.datetime(2021, 1, 4, 0, 5, tzinfo=datetime.timezone.utc),
            ),
            (SQLTimestampModel.ts_1, SQLTimestampModel.ts_2),
        ],
    )
    async def test_date_diff_seconds(
        self,
        session: AsyncSession,
        ts_1: Union[datetime.datetime, sa.Column[datetime.datetime]],
        ts_2: Union[datetime.datetime, sa.Column[datetime.datetime]],
    ):
        result = await session.scalar(
            sa.select(sa.func.date_diff_seconds(ts_2, ts_1)).select_from(
                SQLTimestampModel
            )
        )
        assert pytest.approx(result) == 259500.0  # 3 days and 5 minutes in seconds

    async def test_date_diff_seconds_from_now_literal(self, session: AsyncSession):
        value = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
            seconds=17
        )
        result: Optional[float] = await session.scalar(
            sa.select(sa.func.date_diff_seconds(value))
        )
        assert result is not None
        # database rounnd-trips can be sloooow
        assert 17 <= result <= 17.1

    async def test_date_diff_seconds_from_now_column(self, session: AsyncSession):
        value = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
            seconds=17
        )
        model = SQLTimestampModel(ts_1=value)
        session.add(model)
        await session.commit()

        result: Optional[float] = await session.scalar(
            sa.select(sa.func.date_diff_seconds(SQLTimestampModel.ts_1)).where(
                SQLTimestampModel.id == model.id
            )
        )
        assert result is not None
        # database rounnd-trips can be sloooow
        assert 17 <= result <= 17.1


async def test_error_thrown_if_sqlite_version_is_below_minimum():
    with mock.patch.object(sqlite3, "sqlite_version_info", (3, 23, 9)):
        with mock.patch.object(sqlite3, "sqlite_version", "3.23.9"):
            with pytest.raises(
                RuntimeError,
                match="Prefect requires sqlite >= 3.24.0 but we found version 3.23.9",
            ):
                db = PrefectDBInterface(
                    database_config=AioSqliteConfiguration(
                        connection_url="sqlite+aiosqlite:///file::memory",
                    ),
                    query_components=AioSqliteQueryComponents(),
                    orm=AioSqliteORMConfiguration(),
                )
                await db.engine()


def test_bind_params_from_clause() -> None:
    bp = sa.bindparam("foo", 42, sa.Integer)
    statement = 17 < bp
    assert bindparams_from_clause(statement) == {"foo": bp}
