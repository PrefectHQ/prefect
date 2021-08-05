import pytest
import datetime
import pendulum

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
from prefect.orion.utilities.database import Pydantic, Timestamp
import pydantic

DBBase = declarative_base()


class PydanticModel(pydantic.BaseModel):
    x: int
    y: datetime.datetime = pydantic.Field(default_factory=pendulum.now)


class SQLAlchemyPydanticModel(DBBase):
    __tablename__ = "_test_sqlalchemy_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    data = sa.Column(Pydantic(PydanticModel))


class TestPydantic:
    @pytest.fixture(autouse=True, scope="class")
    async def create_models(self, database_engine):
        async with database_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.create_all)
            try:
                yield
            finally:
                await conn.run_sync(DBBase.metadata.drop_all)

    async def test_write_to_Pydantic(self, database_session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data=p_model)
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)
        assert results[0].data.y < pendulum.now()

    async def test_write_dict_to_Pydantic(self, database_session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyPydanticModel(data=p_model.dict())
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)

    async def test_nullable_Pydantic(self, database_session):
        s_model = SQLAlchemyPydanticModel(data=None)
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyPydanticModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert results[0].data is None


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

    async def test_error_if_naive_timestamp_passed(self, database_session):
        model = SQLAlchemyTimestampModel(ts=datetime.datetime(2000, 1, 1))
        database_session.add(model)
        with pytest.raises(sa.exc.StatementError, match="(must have a timezone)"):
            await database_session.flush()

    async def test_timestamp_converted_to_utc(self, database_session):
        model = SQLAlchemyTimestampModel(
            ts=datetime.datetime(2000, 1, 1, tzinfo=pendulum.timezone("EST"))
        )
        database_session.add(model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyTimestampModel))
        results = query.scalars().all()
        assert results[0].ts == model.ts
        # when this test is run against SQLite, the timestamp will be returned in UTC
        assert results[0].ts.tzinfo == pendulum.timezone("UTC")
