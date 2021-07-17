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
    offset: int = 0,
    limit: int = 10,
    order_by: List[str] = None,
) -> List[orm.Flow]:
    query = select(orm.Flow).offset(offset).limit(limit)
    if order_by:
        order_by_clauses = []
        for clause in order_by:
            if clause.startswith("-"):
                order_by_clauses.append(getattr(orm.Flow, clause[1:]).desc())
            else:
                order_by_clauses.append(getattr(orm.Flow, clause).asc())
        query = query.order_by(*order_by_clauses)
    result = await session.execute(query)
    return result.scalars().all()


async def delete_flow(session: sa.orm.Session, id: str) -> bool:
    result = await session.execute(delete(orm.Flow).where(orm.Flow.id == id))
    return result.rowcount > 0
