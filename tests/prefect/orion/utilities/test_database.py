import pytest
import datetime
import pendulum

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
from prefect.orion.utilities.database import Pydantic
import pydantic

DBBase = declarative_base()


class PydanticModel(pydantic.BaseModel):
    x: int
    y: datetime.datetime = pydantic.Field(default_factory=pendulum.now)


class SQLAlchemyModel(DBBase):
    __tablename__ = "_test_sqlalchemy_model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    data = sa.Column(Pydantic(PydanticModel))


class TestPydantic:
    @pytest.fixture(autouse=True)
    async def create_models(self, database_engine):
        async with database_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.create_all)

    async def test_write_to_Pydantic(self, database_session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyModel(data=p_model)
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)
        assert results[0].data.y < pendulum.now()

    async def test_write_dict_to_Pydantic(self, database_session):
        p_model = PydanticModel(x=100)
        s_model = SQLAlchemyModel(data=p_model.dict())
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert isinstance(results[0].data, PydanticModel)

    async def test_nullable_Pydantic(self, database_session):
        s_model = SQLAlchemyModel(data=None)
        database_session.add(s_model)
        await database_session.flush()

        # clear cache
        database_session.expire_all()

        query = await database_session.execute(sa.select(SQLAlchemyModel))
        results = query.scalars().all()
        assert len(results) == 1
        assert results[0].data is None
