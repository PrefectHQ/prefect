from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

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


async def read_flow(session: sa.orm.Session, id: str) -> orm.Flow:
    return await session.get(orm.Flow, id)


async def read_flows(
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
) -> List[orm.Flow]:

    query = select(orm.Flow).order_by(orm.Flow.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


async def delete_flow(session: sa.orm.Session, id: str) -> bool:
    result = await session.execute(delete(orm.Flow).where(orm.Flow.id == id))
    return result.rowcount > 0
