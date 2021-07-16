import sqlalchemy as sa
from sqlalchemy import select

from prefect.orion.models import orm


async def create_flow(session: sa.orm.Session, name: str) -> orm.Flow:
    try:
        nested = await session.begin_nested()
        flow = orm.Flow(name=name)
        session.add(flow)
        await session.flush()
        return flow
    except:
        await nested.rollback()
        stmt = await session.execute(select(orm.Flow).filter_by(name=name))
        return stmt.scalar()
