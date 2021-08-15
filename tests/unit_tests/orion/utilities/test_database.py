import datetime
from typing import List

import pendulum
import pydantic
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

from prefect.orion.utilities.database import Pydantic, Timestamp

DBBase = declarative_base()


class PydanticModel(pydantic.BaseModel):
    x: int
    y: datetime.datetime = pydantic.Field(default_factory=lambda: pendulum.now("UTC"))


class SQLAlchemyPydanticModel(DBBase):
    __tablename__ = "_test_sqlalchemy_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    data = sa.Column(Pydantic(PydanticModel))
    data_list = sa.Column(Pydantic(List[PydanticModel]))


class TestPydantic:
    @pytest.fixture(autouse=True, scope="class")
    async def create_models(self, database_engine):
        async with database_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.create_all)
            try:
                yield
            finally:
                await conn.run_sync(DBBase.metadata.drop_all)

    async def test_write_to_Pydantic(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data=p_model)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)
        assert results[0].data.y < pendulum.now("UTC")

    async def test_write_dict_to_Pydantic(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data=p_model.dict())
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)

    async def test_nullable_Pydantic(self, session):
        s_model = SQLAlchemyPydanticModel(data=None)
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert results[0].data is None

    async def test_generic_model(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data_list=[p_model])
        session.add(s_model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data_list[0], PydanticModel)
        assert results[0].data_list == [p_model]

    async def test_generic_model_validates(self, session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data_list=p_model)
        session.add(s_model)
        with pytest.raises(sa.exc.StatementError, match="(validation error)"):
            await session.flush()


class SQLAlchemyTimestampModel(DBBase):
    __tablename__ = "_test_timestamp_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    ts = sa.Column(Timestamp)


class TestTimestamp:
    @pytest.fixture(autouse=True, scope="class")
    async def create_models(self, database_engine):
        async with database_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.create_all)
            try:
                yield
            finally:
                await conn.run_sync(DBBase.metadata.drop_all)

    async def test_error_if_naive_timestamp_passed(self, session):
        model = SQLAlchemyTimestampModel(ts=datetime.datetime(2000, 1, 1))
        session.add(model)
        with pytest.raises(sa.exc.StatementError, match="(must have a timezone)"):
            await session.flush()

    async def test_timestamp_converted_to_utc(self, session):
        model = SQLAlchemyTimestampModel(
            ts=datetime.datetime(2000, 1, 1, tzinfo=pendulum.timezone("EST"))
        )
        session.add(model)
        await session.flush()

        # clear cache
        session.expire_all()

        query = await session.execute(sa.select(SQLAlchemyTimestampModel))
        results = query.scalars().all()
        assert results[0].ts == model.ts
        # when this test is run against SQLite, the timestamp will be returned in UTC
        assert results[0].ts.tzinfo == pendulum.timezone("UTC")
